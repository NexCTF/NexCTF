"""Tests for resetting a user's sessions when they are granted admin."""

from sqlalchemy import select

from nexctf.api.scope import grantable_scopes
from nexctf.api.security import create_api_token
from nexctf.model import Event, UserRole

from ..base import second_device


async def _promote(admin, user) -> dict:
    resp = await admin.put(
        f"/admin/user/{user.id}", json={"id": str(user.id), "role": "admin"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _update_event(db_session) -> Event:
    return (
        await db_session.execute(
            select(Event).where(Event.event_type == "admin.user_updated")
        )
    ).scalar_one()


class TestPromotion:
    async def test_signs_the_user_out_everywhere(
        self, admin_client, user_client, client_factory
    ):
        admin, _ = admin_client
        player, user = user_client
        assert (await player.get("/admin/user")).status_code == 403

        assert (await _promote(admin, user))["sessions_revoked"] is True

        assert (await player.get("/info/me")).status_code == 401
        assert (await player.get("/admin/user")).status_code == 401
        async with second_device(client_factory, user.username, "userpass") as fresh:
            assert (await fresh.get("/admin/user")).status_code == 200

    async def test_is_recorded_on_the_event(
        self, admin_client, user_client, db_session
    ):
        admin, _ = admin_client
        _, user = user_client
        await _promote(admin, user)

        assert (await _update_event(db_session)).meta["sessions_revoked"] == "true"

    async def test_other_fields_revoke_nothing(self, admin_client, user_client):
        admin, _ = admin_client
        player, user = user_client
        resp = await admin.put(
            f"/admin/user/{user.id}",
            json={"id": str(user.id), "username": "renamed", "role": "user"},
        )
        assert resp.json()["data"]["sessions_revoked"] is False

        assert (await player.get("/info/me")).status_code == 200

    async def test_admin_to_admin_revokes_nothing(
        self, admin_client, signed_in_client, db_session
    ):
        admin, _ = admin_client
        async with signed_in_client("other_admin", "otherpass", UserRole.admin) as (
            other,
            other_user,
        ):
            assert (await _promote(admin, other_user))["sessions_revoked"] is False

            assert (await other.get("/admin/user")).status_code == 200
        assert "sessions_revoked" not in (await _update_event(db_session)).meta


class TestPlayerTokenAfterPromotion:
    async def test_gains_no_admin_scope(self, admin_client, user_client, http_client):
        admin, _ = admin_client
        _, user = user_client
        raw, _ = await create_api_token(user.id, scopes=sorted(grantable_scopes(False)))
        headers = {"Authorization": f"Bearer {raw}"}

        await _promote(admin, user)

        resp = await http_client.get("/admin/user", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SCOPE-403"
        assert (await http_client.get("/info/me", headers=headers)).status_code == 200
