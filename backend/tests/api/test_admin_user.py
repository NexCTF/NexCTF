"""Tests for /admin/user endpoints (list, get, create, update, delete)."""

import hashlib
from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Team, User

from ..base import (
    NULL_UUID,
    CreateGuardMixin,
    DeleteGuardMixin,
    GetItemGuardMixin,
    ListGuardMixin,
    UpdateGuardMixin,
)


class TestCreateUser(CreateGuardMixin):
    PREFIX = "/admin/user"

    async def test_create_works_with_registration_disabled(
        self,
        admin_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        config_overrides["ctf.allow_registration"] = "false"
        c, _ = admin_client
        resp = await c.post(
            self.PREFIX,
            json={
                "username": "made-by-admin",
                "password": "s3cret-pass",
                "role": "moderator",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["username"] == "made-by-admin"
        assert data["role"] == "moderator"
        # Admin hands the password over out of band, so the account is usable now.
        assert data["email_verified"] is True
        assert data["has_password"] is True

    async def test_create_duplicate_username(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_members: list[User],
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            self.PREFIX,
            json={
                "username": fixture_user_members[0].username,
                "password": "s3cret-pass",
            },
        )
        assert resp.status_code == 409

    async def test_create_duplicate_email(
        self,
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = admin_client
        body = {"username": "dup-a", "password": "s3cret-pass", "email": "dup@test.com"}
        assert (await c.post(self.PREFIX, json=body)).status_code == 201
        resp = await c.post(self.PREFIX, json={**body, "username": "dup-b"})
        assert resp.status_code == 409

    async def test_create_with_custom_fields(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        """Values sent on create land in the same transaction as the user."""
        c, _ = admin_client
        dresp = await c.post(
            "/admin/custom-field",
            json={"name": "discord", "label": "Discord", "target": "user"},
        )
        assert dresp.status_code == 200
        definition_id = dresp.json()["data"]["id"]

        resp = await c.post(
            self.PREFIX,
            json={
                "username": "cf-user",
                "password": "s3cret-pass",
                "custom_fields": {definition_id: "player#1"},
            },
        )
        assert resp.status_code == 201

        detail = await c.get(f"{self.PREFIX}/{resp.json()['data']['id']}")
        values = detail.json()["data"]["custom_field_values"]
        assert [(v["definition"]["id"], v["value"]) for v in values] == [
            (definition_id, "player#1")
        ]


class TestListUsers(ListGuardMixin):
    PREFIX = "/admin/user"

    async def test_list_has_admin(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, admin = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        ids = [u["id"] for u in resp.json()["data"]]
        assert str(admin.id) in ids

    async def test_list_multiple_users(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_admin: list[User],
        fixture_user_members: list[User],
        fixture_user_moderator: list[User],
    ) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        # 4 fixture users + admin_client's own user
        assert resp.json()["pagination"]["total_count"] >= 5


class TestGetUser(GetItemGuardMixin):
    PREFIX = "/admin/user"

    async def test_get_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_members: list[User],
    ) -> None:
        c, _ = admin_client
        u = fixture_user_members[0]
        resp = await c.get(f"{self.PREFIX}/{u.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == u.username
        assert data["role"] == "user"
        assert data["is_active"] is True

    async def test_get_not_found(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404


class TestUpdateUser(UpdateGuardMixin):
    PREFIX = "/admin/user"

    async def test_update_username(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_members: list[User],
    ) -> None:
        c, _ = admin_client
        u = fixture_user_members[0]
        resp = await c.put(
            f"{self.PREFIX}/{u.id}",
            json={"id": str(u.id), "username": "new-name"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["username"] == "new-name"

    async def test_update_role(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_members: list[User],
    ) -> None:
        c, _ = admin_client
        u = fixture_user_members[0]  # regular user → promote to moderator
        resp = await c.put(
            f"{self.PREFIX}/{u.id}",
            json={"id": str(u.id), "role": "moderator"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "moderator"

    async def test_deactivate_user(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_members: list[User],
    ) -> None:
        c, _ = admin_client
        u = fixture_user_members[0]
        resp = await c.put(
            f"{self.PREFIX}/{u.id}",
            json={"id": str(u.id), "is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is False

    async def test_assign_team(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
        fixture_user_admin: list[User],
    ) -> None:
        c, _ = admin_client
        t = fixture_team[0]
        u = fixture_user_admin[0]  # fx_admin — has no team_id
        resp = await c.put(
            f"{self.PREFIX}/{u.id}",
            json={"id": str(u.id), "team_id": str(t.id)},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["team_id"] == str(t.id)
        assert data["team_name"] == t.name

    async def test_update_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.put(f"{self.PREFIX}/{NULL_UUID}", json={"id": NULL_UUID})
        assert resp.status_code == 404

    async def test_update_email_resets_verification(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        fixture_user_members: list[User],
    ) -> None:
        """Changing a verified user's email must not carry over its verified status."""
        c, _ = admin_client
        u = fixture_user_members[0]
        u.email = "old@test.com"
        u.email_verified = True
        await db_session.flush()

        resp = await c.put(
            f"{self.PREFIX}/{u.id}",
            json={"id": str(u.id), "email": "new@test.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["email_verified"] is False

        await db_session.refresh(u)
        assert u.email == "new@test.com"
        assert u.email_verified is False

    async def test_update_same_email_keeps_verification(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        fixture_user_members: list[User],
    ) -> None:
        c, _ = admin_client
        u = fixture_user_members[0]
        u.email = "same@test.com"
        u.email_verified = True
        await db_session.flush()

        resp = await c.put(
            f"{self.PREFIX}/{u.id}",
            json={"id": str(u.id), "email": "same@test.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["email_verified"] is True


class TestAdminResetTotp:
    PREFIX = "/admin/user"

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.post(f"{self.PREFIX}/{NULL_UUID}/totp/reset")
        assert resp.status_code == 403

    async def test_reset_totp_clears_secret(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        fixture_user_with_totp: list[User],
    ) -> None:
        c, _ = admin_client
        user = fixture_user_with_totp[0]

        resp = await c.post(f"{self.PREFIX}/{user.id}/totp/reset")
        assert resp.status_code == 204

        await db_session.refresh(user)
        assert user.totp_secret is None

    async def test_reset_totp_idempotent_when_not_enabled(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_members: list[User],
    ) -> None:
        c, _ = admin_client
        user = fixture_user_members[0]  # fx_user1 — no TOTP secret

        resp = await c.post(f"{self.PREFIX}/{user.id}/totp/reset")
        assert resp.status_code == 204

    async def test_reset_totp_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(f"{self.PREFIX}/{NULL_UUID}/totp/reset")
        assert resp.status_code == 404


class TestAdminPasswordResetToken:
    PREFIX = "/admin/user"

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.post(f"{self.PREFIX}/{NULL_UUID}/password-reset-token")
        assert resp.status_code == 403

    async def test_returns_token(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_members: list[User],
        mock_redis,
    ) -> None:
        c, _ = admin_client
        user = fixture_user_members[0]

        mock_redis.setex = AsyncMock(return_value=True)
        resp = await c.post(f"{self.PREFIX}/{user.id}/password-reset-token")
        assert resp.status_code == 200
        token = resp.json()["data"]
        assert token and len(token) > 10

        # Confirm the hashed token was stored in redis
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        mock_redis.setex.assert_called_once_with(
            f"pwd_reset:{token_hash}", 3600, str(user.id)
        )

    async def test_not_found(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(f"{self.PREFIX}/{NULL_UUID}/password-reset-token")
        assert resp.status_code == 404


class TestDeleteUser(DeleteGuardMixin):
    PREFIX = "/admin/user"

    async def test_delete_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_user_moderator: list[User],
    ) -> None:
        c, _ = admin_client
        u = fixture_user_moderator[0]  # fx_moderator — no FK dependencies
        resp = await c.delete(f"{self.PREFIX}/{u.id}")
        assert resp.status_code == 200

        resp2 = await c.get(f"{self.PREFIX}/{u.id}")
        assert resp2.status_code == 404

    async def test_delete_takes_the_rows_the_user_owns(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Tokens, OAuth links and sessions must not block deleting their owner."""
        from datetime import UTC, datetime, timedelta

        from nexctf.model import OAuthAccount, OAuthProvider, UserSession, UserToken

        c, _ = admin_client
        victim = User(username="fk_victim", hashed_password="x")
        provider = OAuthProvider(
            name="IdP",
            slug="fk-idp",
            client_id="c",
            client_secret="s",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
        )
        db_session.add_all([victim, provider])
        await db_session.flush()

        now = datetime.now(UTC)
        db_session.add_all(
            [
                UserToken(user_id=victim.id, token_hash="fk-token-hash", name="t"),
                OAuthAccount(
                    user_id=victim.id, provider_id=provider.id, subject="fk-subject"
                ),
                UserSession(
                    user_id=victim.id,
                    sid_hash="fk-sid-hash",
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                ),
            ]
        )
        await db_session.flush()

        assert (await c.delete(f"{self.PREFIX}/{victim.id}")).status_code == 200
        assert (await c.get(f"{self.PREFIX}/{victim.id}")).status_code == 404

    async def test_delete_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 200  # delete is idempotent
