"""Tests for /admin/user/{uuid}/sessions listing and revocation."""

from sqlalchemy import select

from nexctf.model import Event, UserSession

from ..base import NULL_UUID, DeleteGuardMixin, ListGuardMixin


async def _session_id(db_session, user_id) -> str:
    row = (
        await db_session.execute(
            select(UserSession).where(UserSession.user_id == user_id)
        )
    ).scalar_one()
    return str(row.id)


class TestListUserSessions(ListGuardMixin):
    PREFIX = f"/admin/user/{NULL_UUID}/sessions"

    async def test_lists_the_target_user_sessions(
        self, admin_client, user_client, db_session
    ):
        c, _ = admin_client
        _, user = user_client
        rows = (await c.get(f"/admin/user/{user.id}/sessions")).json()["data"]

        assert [row["id"] for row in rows] == [await _session_id(db_session, user.id)]
        # Another user's session is never the admin's own.
        assert rows[0]["current"] is False

    async def test_marks_the_admins_own_session(self, admin_client):
        c, admin = admin_client
        rows = (await c.get(f"/admin/user/{admin.id}/sessions")).json()["data"]

        assert [r["current"] for r in rows] == [True]


class TestRevokeUserSession(DeleteGuardMixin):
    PREFIX = f"/admin/user/{NULL_UUID}/sessions"

    async def test_revokes_a_session(self, admin_client, user_client, db_session):
        c, admin = admin_client
        uc, user = user_client
        session_id = await _session_id(db_session, user.id)

        resp = await c.delete(f"/admin/user/{user.id}/sessions/{session_id}")

        assert resp.status_code == 204
        assert (await c.get(f"/admin/user/{user.id}/sessions")).json()["data"] == []
        # The revoked cookie no longer authenticates.
        assert (await uc.get("/me/profile")).status_code == 401
        event = (
            await db_session.execute(
                select(Event).where(Event.event_type == "admin.user_session_revoked")
            )
        ).scalar_one()
        assert event.actor_id == admin.id
        assert event.meta["target_username"] == user.username

    async def test_cannot_revoke_across_users(
        self, admin_client, user_client, db_session
    ):
        """The session id alone must not be enough; it has to belong to the user."""
        c, admin = admin_client
        _, user = user_client
        victim_session = await _session_id(db_session, user.id)

        resp = await c.delete(f"/admin/user/{admin.id}/sessions/{victim_session}")

        assert resp.status_code == 404
        assert len((await c.get(f"/admin/user/{user.id}/sessions")).json()["data"]) == 1

    async def test_unknown_user_is_404(self, admin_client, user_client, db_session):
        c, _ = admin_client
        _, user = user_client
        session_id = await _session_id(db_session, user.id)

        resp = await c.delete(f"/admin/user/{NULL_UUID}/sessions/{session_id}")

        assert resp.status_code == 404
