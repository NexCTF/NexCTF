"""Tests for per-device session listing and revocation."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select

from nexctf.core.config import settings
from nexctf.model import UserSession

from ..base import NULL_UUID

COOKIE = "NexCTF"


@asynccontextmanager
async def _second_device(client_factory, username: str, password: str):
    """Log the same user in from a second client, as another browser would."""
    async with client_factory() as c:
        resp = await c.post(
            "/auth/token", data={"username": username, "password": password}
        )
        assert resp.status_code == 204
        yield c


def _sessions(resp) -> list[dict]:
    return resp.json()["data"]


class TestListSessions:
    async def test_requires_auth(self, http_client: AsyncClient):
        assert (await http_client.get("/me/sessions")).status_code == 401

    async def test_marks_the_requesting_session(self, user_client):
        c, _ = user_client
        rows = _sessions(await c.get("/me/sessions"))
        assert len(rows) == 1
        assert rows[0]["current"] is True

    async def test_lists_every_device(self, user_client, client_factory):
        c, _ = user_client
        async with _second_device(client_factory, "test_user", "userpass"):
            rows = _sessions(await c.get("/me/sessions"))
            assert len(rows) == 2
            assert [r["current"] for r in rows].count(True) == 1

    async def test_over_long_user_agent_does_not_break_login(
        self, client_factory, db_session, override_db_context
    ):
        """The UA header is client-controlled; it must not overflow the column."""
        from nexctf.api.security import hash_password
        from nexctf.model import User, UserRole

        db_session.add(
            User(
                username="long_ua",
                hashed_password=hash_password("uapass"),
                role=UserRole.user,
            )
        )
        await db_session.flush()

        async with client_factory() as c:
            resp = await c.post(
                "/auth/token",
                data={"username": "long_ua", "password": "uapass"},
                headers={"user-agent": "M" * 2000},
            )
            assert resp.status_code == 204
            assert len(_sessions(await c.get("/me/sessions"))[0]["user_agent"]) == 512

    async def test_records_ip_and_user_agent(self, user_client):
        c, _ = user_client
        rows = _sessions(await c.get("/me/sessions"))
        assert rows[0]["user_agent"] is not None
        assert rows[0]["ip"] is not None
        assert rows[0]["last_ip"] == rows[0]["ip"]

    async def test_last_ip_follows_the_session_and_ip_keeps_the_origin(
        self, user_client, db_session
    ):
        """A cookie replayed elsewhere shows the new location."""
        c, user = user_client
        origin = _sessions(await c.get("/me/sessions"))[0]["ip"]

        with patch.object(settings, "TRUSTED_PROXY_COUNT", 1):
            resp = await c.get("/info/me", headers={"X-Forwarded-For": "198.51.100.9"})
            assert resp.status_code == 200

        ip, last_ip = (
            await db_session.execute(
                select(UserSession.ip, UserSession.last_ip).where(
                    UserSession.user_id == user.id
                )
            )
        ).one()
        assert ip == origin
        assert last_ip == "198.51.100.9"


class TestRevokeSession:
    async def test_revoking_one_device_leaves_the_other(
        self, user_client, client_factory
    ):
        c, _ = user_client
        async with _second_device(client_factory, "test_user", "userpass") as other:
            target = next(
                r for r in _sessions(await c.get("/me/sessions")) if not r["current"]
            )
            assert (await c.delete(f"/me/sessions/{target['id']}")).status_code == 204

            assert (await other.get("/info/me")).status_code == 401
            assert (await c.get("/info/me")).status_code == 200
            assert len(_sessions(await c.get("/me/sessions"))) == 1

    async def test_cannot_revoke_another_users_session(self, user_client, admin_client):
        c, _ = user_client
        admin_c, _ = admin_client
        mine = _sessions(await c.get("/me/sessions"))[0]
        assert (await admin_c.delete(f"/me/sessions/{mine['id']}")).status_code == 404
        assert (await c.get("/info/me")).status_code == 200

    async def test_unknown_session_is_404(self, user_client):
        c, _ = user_client
        assert (await c.delete(f"/me/sessions/{NULL_UUID}")).status_code == 404


class TestRevokeAllSessions:
    async def test_requires_auth(self, http_client: AsyncClient):
        assert (await http_client.delete("/me/sessions")).status_code == 401

    async def test_signs_out_every_device_including_this_one(
        self, user_client, client_factory
    ):
        """The stolen-cookie escape hatch: end every session without guessing."""
        c, _ = user_client
        async with _second_device(client_factory, "test_user", "userpass") as other:
            captured = c.cookies[COOKIE]
            assert (await c.delete("/me/sessions")).status_code == 204

            assert (await other.get("/info/me")).status_code == 401
            # Even replayed, the requesting session's own cookie is dead.
            c.cookies.set(COOKIE, captured)
            assert (await c.get("/info/me")).status_code == 401

    async def test_clears_the_cookie(self, user_client):
        c, _ = user_client
        resp = await c.delete("/me/sessions")
        assert resp.status_code == 204
        assert COOKIE not in c.cookies


class TestLogoutRevokesServerSide:
    """NEXCTF-13: a cookie captured before logout must stop working."""

    async def test_logout_kills_only_this_device(self, user_client, client_factory):
        c, _ = user_client
        async with _second_device(client_factory, "test_user", "userpass") as other:
            captured = c.cookies[COOKIE]
            assert (await c.post("/auth/logout")).status_code == 204

            assert (await other.get("/info/me")).status_code == 200
            assert len(_sessions(await other.get("/me/sessions"))) == 1

            # Replaying the still-signed cookie must not resurrect the session.
            c.cookies.set(COOKIE, captured)
            assert (await c.get("/info/me")).status_code == 401


class TestPasswordChangeRevokesOthers:
    async def test_other_devices_are_signed_out(self, user_client, client_factory):
        c, _ = user_client
        async with _second_device(client_factory, "test_user", "userpass") as other:
            resp = await c.post(
                "/me/password",
                json={"current_password": "userpass", "new_password": "newpass123"},
            )
            assert resp.status_code == 204

            assert (await other.get("/info/me")).status_code == 401
            assert (await c.get("/info/me")).status_code == 200
            assert len(_sessions(await c.get("/me/sessions"))) == 1


class TestExpiry:
    async def test_expired_session_is_rejected(self, user_client, db_session):
        c, user = user_client
        row = (
            await db_session.execute(
                select(UserSession).where(UserSession.user_id == user.id)
            )
        ).scalar_one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.flush()

        assert (await c.get("/info/me")).status_code == 401
