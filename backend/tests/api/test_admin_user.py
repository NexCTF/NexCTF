"""Tests for /admin/user endpoints (list, get, update, delete — no create)."""

import hashlib

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from nexctf.model import Team, User

from ..base import (
    NULL_UUID,
    DeleteGuardMixin,
    GetItemGuardMixin,
    ListGuardMixin,
    UpdateGuardMixin,
)


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

    async def test_delete_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 200  # delete is idempotent
