"""Tests for the re-authentication window on sensitive actions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from nexctf.api.security import REAUTH_WINDOW, create_api_token
from nexctf.model import Event, OAuthAccount, OAuthProvider, UserRole
from nexctf.module.session import FAILED_LOGIN_EVENT

from ..base import NULL_UUID, FakeIdP, session_row

COOKIE = "NexCTF"
REAUTH_CODE = "AUTH-REAUTH-REQUIRED"


PASSWORD = "secretpass"
BACKUP_KEY = "backups/nexctf-20260908T143005Z-manual.dump"
STALE = REAUTH_WINDOW + 100


@pytest.fixture
async def stale_user(signed_in_client):
    async with signed_in_client("stale_user", PASSWORD, UserRole.user, age=STALE) as c:
        yield c


@pytest.fixture
async def stale_admin(signed_in_client):
    async with signed_in_client(
        "stale_admin", PASSWORD, UserRole.admin, age=STALE
    ) as c:
        yield c


def _is_reauth(resp) -> bool:
    return resp.status_code == 401 and resp.json()["error_code"] == REAUTH_CODE


async def _reauth(c: AsyncClient, **body: str) -> None:
    resp = await c.post("/auth/reauth", json={"password": PASSWORD, **body})
    assert resp.status_code == 204, resp.text


PLAYER_GATES = [
    ("POST", "/me/tokens", {"name": "t", "scopes": ["read:challenges"]}),
    ("POST", "/me/totp/setup", None),
    ("POST", "/me/totp/enable", {"code": "000000"}),
    ("POST", "/me/totp/disable", {"code": "000000"}),
    ("DELETE", f"/me/oauth/{NULL_UUID}", None),
    ("POST", "/me/password", {"current_password": "x", "new_password": "newpass123"}),
]

ADMIN_GATES = [
    (
        "POST",
        "/admin/user",
        {"username": "new_admin", "password": "newpass123", "role": "admin"},
    ),
    ("PUT", f"/admin/user/{NULL_UUID}", {"id": NULL_UUID, "role": "admin"}),
    ("POST", f"/admin/user/{NULL_UUID}/totp/reset", None),
    ("POST", f"/admin/user/{NULL_UUID}/password-reset-token", None),
    ("DELETE", f"/admin/user/{NULL_UUID}", None),
    ("POST", "/admin/backup/restore?key=..", None),
    ("DELETE", "/admin/backup?key=..", None),
    ("POST", f"/admin/backup/download?key={BACKUP_KEY}", None),
    ("POST", "/admin/oauth-provider", {"slug": "x"}),
    ("PUT", f"/admin/oauth-provider/{NULL_UUID}", {"name": "x"}),
    ("DELETE", f"/admin/oauth-provider/{NULL_UUID}", None),
    ("POST", "/admin/oauth-client", {"name": "x"}),
    ("PUT", f"/admin/oauth-client/{NULL_UUID}", {"name": "x"}),
    ("DELETE", f"/admin/oauth-client/{NULL_UUID}", None),
    ("PUT", "/admin/config", {"items": {"ctf.allow_registration": "false"}}),
    ("PUT", "/admin/config", {"items": {"email.smtp_host": "evil.example"}}),
    ("PUT", "/admin/config", {"items": {"appearance.custom_css": "body{}"}}),
]


class TestGates:
    @pytest.mark.parametrize(("method", "path", "body"), PLAYER_GATES)
    async def test_player_action_needs_fresh_session(
        self, stale_user, method: str, path: str, body: dict | None
    ):
        c, _ = stale_user
        resp = await c.request(method, path, json=body)
        assert _is_reauth(resp), resp.text
        assert resp.json()["data"] == {"max_age": REAUTH_WINDOW}

        await _reauth(c)
        assert not _is_reauth(await c.request(method, path, json=body))

    @pytest.mark.parametrize(("method", "path", "body"), ADMIN_GATES)
    async def test_admin_action_needs_fresh_session(
        self, stale_admin, method: str, path: str, body: dict | None
    ):
        c, _ = stale_admin
        assert _is_reauth(await c.request(method, path, json=body))

        await _reauth(c)
        assert not _is_reauth(await c.request(method, path, json=body))

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("GET", "/me/tokens", None),
            ("GET", "/me/sessions", None),
            ("DELETE", "/me/sessions", None),
            ("PUT", "/me/profile", {"links": [], "custom_fields": {}}),
        ],
    )
    async def test_ordinary_action_accepts_stale_session(
        self, stale_user, method: str, path: str, body: dict | None
    ):
        c, _ = stale_user
        assert not _is_reauth(await c.request(method, path, json=body))

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("PUT", "/admin/config", {"items": {"ctf.name": "Renamed"}}),
            (
                "PUT",
                f"/admin/user/{NULL_UUID}",
                {"id": NULL_UUID, "username": "renamed"},
            ),
            (
                "POST",
                "/admin/user",
                {"username": "player", "password": "newpass123", "role": "user"},
            ),
        ],
    )
    async def test_conditional_gate_skips_harmless_change(
        self, stale_admin, method: str, path: str, body: dict
    ):
        c, _ = stale_admin
        assert not _is_reauth(await c.request(method, path, json=body))

    @pytest.mark.parametrize("change", [{"role": "user"}, {"is_active": False}])
    async def test_disarming_an_admin_needs_fresh_session(
        self, stale_admin, admin_client, change: dict
    ):
        c, _ = stale_admin
        _, target = admin_client
        path = f"/admin/user/{target.id}"
        body = {"id": str(target.id), **change}
        assert _is_reauth(await c.put(path, json=body))

        await _reauth(c)
        assert (await c.put(path, json=body)).status_code == 200

    async def test_deactivating_a_player_accepts_stale_session(
        self, stale_admin, user_client
    ):
        c, _ = stale_admin
        _, player = user_client
        resp = await c.put(
            f"/admin/user/{player.id}", json={"id": str(player.id), "is_active": False}
        )
        assert resp.status_code == 200

    async def test_window_edge_is_still_fresh(self, signed_in_client):
        async with signed_in_client(
            "edge", PASSWORD, UserRole.user, age=REAUTH_WINDOW - 30
        ) as (c, _):
            assert not _is_reauth(await c.post("/me/totp/setup"))

    async def test_revoked_session_gets_plain_401(self, stale_user, db_session):
        c, user = stale_user
        row = await session_row(db_session, user)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.flush()

        resp = await c.post("/me/totp/setup")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH-401"


class TestApiTokens:
    async def test_token_skips_window_where_tokens_are_accepted(
        self, stale_admin, http_client
    ):
        _, admin = stale_admin
        raw, _ = await create_api_token(admin.id, scopes=["write:admin.user"])
        resp = await http_client.delete(
            f"/admin/user/{NULL_UUID}", headers={"Authorization": f"Bearer {raw}"}
        )
        assert resp.status_code == 200

    async def test_token_still_refused_on_session_only_action(
        self, stale_user, http_client
    ):
        _, user = stale_user
        raw, _ = await create_api_token(user.id, scopes=["write:profile"])
        resp = await http_client.post(
            "/me/totp/setup", headers={"Authorization": f"Bearer {raw}"}
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SCOPE-403-SESSION"

    async def test_reauth_refuses_token(self, stale_user, http_client):
        _, user = stale_user
        raw, _ = await create_api_token(user.id, scopes=["write:profile"])
        resp = await http_client.post(
            "/auth/reauth",
            json={"password": PASSWORD},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert resp.status_code == 403


class TestReauthEndpoint:
    async def test_keeps_thesession_row(self, stale_user, db_session):
        c, user = stale_user
        before = await session_row(db_session, user)
        row_id, old_hash, expires_at = before.id, before.sid_hash, before.expires_at
        old_cookie = c.cookies[COOKIE]

        await _reauth(c)

        after = await session_row(db_session, user)
        assert after.id == row_id
        assert after.sid_hash != old_hash
        assert after.expires_at == expires_at
        assert len((await c.get("/me/sessions")).json()["data"]) == 1

        c.cookies.set(COOKIE, old_cookie)
        assert (await c.get("/info/me")).status_code == 401

    async def test_does_not_outlive_the_session(self, stale_user, db_session):
        c, user = stale_user
        await _reauth(c)
        row = await session_row(db_session, user)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.flush()

        assert (await c.get("/info/me")).status_code == 401

    async def test_wrong_password(self, stale_user, db_session):
        c, _ = stale_user
        resp = await c.post("/auth/reauth", json={"password": "nope"})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH-401"
        assert _is_reauth(await c.post("/me/totp/setup"))

        events = (
            await db_session.execute(
                select(Event).where(Event.event_type == FAILED_LOGIN_EVENT)
            )
        ).scalars()
        assert [e.meta["reason"] for e in events] == ["reauth_bad_password"]

    async def test_logs_success(self, stale_user, db_session):
        c, user = stale_user
        await _reauth(c)
        event = (
            await db_session.execute(
                select(Event).where(Event.event_type == "user.reauth")
            )
        ).scalar_one()
        assert event.actor_id == user.id

    async def test_rate_limited(self, stale_user, mock_redis):
        c, _ = stale_user
        mock_redis.pipeline.return_value.execute = AsyncMock(
            return_value=[None, None, 11, None]
        )
        resp = await c.post("/auth/reauth", json={"password": PASSWORD})
        assert resp.status_code == 429

    async def test_requires_a_session(self, http_client):
        resp = await http_client.post("/auth/reauth", json={"password": "x"})
        assert resp.status_code == 401


class TestReauthWithTotp:
    @pytest.fixture
    async def stale_totp_user(self, signed_in_client):
        secret = pyotp.random_base32()
        async with signed_in_client(
            "totp_user", PASSWORD, UserRole.user, age=STALE, totp_secret=secret
        ) as (c, user):
            yield c, user, secret

    async def test_asks_for_the_code(self, stale_totp_user):
        c, _, _ = stale_totp_user
        resp = await c.post("/auth/reauth", json={"password": PASSWORD})
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "AUTH-TOTP-REQUIRED"

    async def test_wrong_code(self, stale_totp_user):
        c, _, _ = stale_totp_user
        resp = await c.post(
            "/auth/reauth", json={"password": PASSWORD, "totp_code": "000000"}
        )
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH-401-OTP"

    async def test_password_and_code(self, stale_totp_user):
        c, _, secret = stale_totp_user
        await _reauth(c, totp_code=pyotp.TOTP(secret).now())
        assert not _is_reauth(await c.post("/me/totp/setup"))

    async def test_code_alone_for_account_without_password(
        self, stale_totp_user, db_session
    ):
        c, user, secret = stale_totp_user
        user.hashed_password = None
        await db_session.flush()
        resp = await c.post(
            "/auth/reauth", json={"totp_code": pyotp.TOTP(secret).now()}
        )
        assert resp.status_code == 204


class TestReauthThroughOAuth:
    @pytest.fixture
    async def stale_oauth_user(self, stale_user, db_session):
        c, user = stale_user
        provider = OAuthProvider(
            slug="test-idp",
            name="Test IdP",
            client_id="cid",
            client_secret="secret",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
            is_active=True,
        )
        db_session.add(provider)
        await db_session.flush()
        db_session.add(
            OAuthAccount(user_id=user.id, provider_id=provider.id, subject="sub-1")
        )
        user.hashed_password = None
        await db_session.flush()
        return c, user

    async def test_password_reauth_is_refused(self, stale_oauth_user):
        c, _ = stale_oauth_user
        resp = await c.post("/auth/reauth", json={"password": PASSWORD})
        assert resp.status_code == 401

    async def test_round_trip_refreshes_the_session_in_place(
        self, stale_oauth_user, db_session
    ):
        c, user = stale_oauth_user
        before = await session_row(db_session, user)
        row_id, expires_at = before.id, before.expires_at

        assert (await FakeIdP("test-idp").login(c, "sub-1")).status_code == 302

        after = await session_row(db_session, user)
        assert (after.id, after.expires_at) == (row_id, expires_at)
        assert not _is_reauth(await c.post("/me/totp/setup"))
