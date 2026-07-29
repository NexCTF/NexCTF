"""Tests for the self-service password change endpoint."""

from nexctf.api.security import verify_password


class TestChangePassword:
    async def test_requires_auth(self, http_client):
        resp = await http_client.post(
            "/me/password",
            json={"current_password": "userpass", "new_password": "newpass123"},
        )
        assert resp.status_code == 401

    async def test_wrong_current_password(self, user_client):
        c, _ = user_client
        resp = await c.post(
            "/me/password",
            json={"current_password": "wrongpass", "new_password": "newpass123"},
        )
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH-401"

    async def test_changes_password_and_keeps_session(self, user_client, db_session):
        c, user = user_client
        resp = await c.post(
            "/me/password",
            json={"current_password": "userpass", "new_password": "newpass123"},
        )
        assert resp.status_code == 204

        await db_session.refresh(user)
        assert user.hashed_password is not None
        assert verify_password("newpass123", user.hashed_password)
        assert user.session_version == 1
        assert (await c.get("/info/me")).status_code == 200

    async def test_me_reports_has_password(self, user_client):
        c, _ = user_client
        resp = await c.get("/info/me")
        assert resp.json()["data"]["has_password"] is True
