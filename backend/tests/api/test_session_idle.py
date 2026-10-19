"""Tests for the idle timeout on browser sessions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import User
from nexctf.module.session import IDLE_TIMEOUT_KEY

from ..base import add_session, session_row

IDLE_MINUTES = 30
IDLE = timedelta(minutes=IDLE_MINUTES)


@pytest.fixture
def config_overrides() -> dict[str, str]:
    return {IDLE_TIMEOUT_KEY: str(IDLE_MINUTES)}


async def _last_seen(db_session: AsyncSession, user: User, ago: timedelta) -> None:
    """Mark the user's session as last used *ago*."""
    row = await session_row(db_session, user)
    row.last_seen_at = datetime.now(UTC) - ago
    await db_session.flush()


async def _idle_device(db_session: AsyncSession, user: User) -> None:
    """Give *user* a second, unexpired session unused for longer than the timeout."""
    await add_session(db_session, user, ip="10.9.9.9", minutes_ago=IDLE_MINUTES + 1)


class TestIdleTimeout:
    async def test_disabled_keeps_a_quiet_session(
        self, user_client, db_session, config_overrides
    ):
        c, user = user_client
        config_overrides[IDLE_TIMEOUT_KEY] = "0"
        await _last_seen(db_session, user, timedelta(hours=10))

        assert (await c.get("/info/me")).status_code == 200

    async def test_just_inside_the_window(self, user_client, db_session):
        c, user = user_client
        await _last_seen(db_session, user, IDLE - timedelta(minutes=1))

        assert (await c.get("/info/me")).status_code == 200
        row = await session_row(db_session, user)
        assert datetime.now(UTC) - row.last_seen_at < timedelta(minutes=1)

    async def test_just_outside_the_window(self, user_client, db_session):
        c, user = user_client
        await _last_seen(db_session, user, IDLE + timedelta(minutes=1))

        first = await c.get("/info/me")
        assert first.status_code == 401
        assert first.json()["error_code"] == "AUTH-401"
        assert (await c.get("/info/me")).status_code == 401

    async def test_activity_does_not_outlive_the_absolute_lifetime(
        self, user_client, db_session
    ):
        c, user = user_client
        row = await session_row(db_session, user)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.flush()

        assert (await c.get("/info/me")).status_code == 401

    async def test_short_timeout_refreshes_often_enough(
        self, user_client, db_session, config_overrides
    ):
        """Below the 5 minute throttle, activity must still keep the session."""
        c, user = user_client
        config_overrides[IDLE_TIMEOUT_KEY] = "1"
        await _last_seen(db_session, user, timedelta(seconds=40))

        assert (await c.get("/info/me")).status_code == 200
        row = await session_row(db_session, user)
        assert datetime.now(UTC) - row.last_seen_at < timedelta(seconds=10)


class TestIdleSessionsAreNotLive:
    async def test_my_sessions(self, user_client, db_session):
        c, user = user_client
        await _idle_device(db_session, user)

        rows = (await c.get("/me/sessions")).json()["data"]
        assert [row["current"] for row in rows] == [True]

    async def test_admin_user_sessions(self, admin_client, user_client, db_session):
        c, _ = admin_client
        _, user = user_client
        await _idle_device(db_session, user)

        rows = (await c.get(f"/admin/user/{user.id}/sessions")).json()["data"]
        assert len(rows) == 1

    async def test_admin_live_addresses(self, admin_client, user_client, db_session):
        c, _ = admin_client
        _, user = user_client
        await _idle_device(db_session, user)

        overview = (await c.get("/admin/session/addresses")).json()["data"]
        assert "10.9.9.9" not in {row["ip"] for row in overview["addresses"]}
        assert overview["session_count"] == 2

    async def test_admin_user_detail(self, admin_client, user_client, db_session):
        c, _ = admin_client
        _, user = user_client
        await _idle_device(db_session, user)

        ips = (await c.get(f"/admin/user/{user.id}")).json()["data"]["ips"]
        assert "10.9.9.9" not in {row["ip"] for row in ips}
