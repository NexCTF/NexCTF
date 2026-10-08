"""Tests for the challenge.viewed event emitted on a player's first open."""

from __future__ import annotations

from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Event, User
from nexctf.module.challenge.view import VIEWED_KEY_PREFIX
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from tests.base import put_in_team


async def _challenge(db_session: AsyncSession) -> StandardChallenge:
    challenge = StandardChallenge(title="Viewed", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    return challenge


async def _views(db_session: AsyncSession) -> list[Event]:
    rows = await db_session.scalars(
        select(Event).where(Event.event_type == "challenge.viewed")
    )
    return list(rows.all())


class TestChallengeViewed:
    async def test_first_open_is_recorded(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        mock_redis,
    ) -> None:
        c, user = user_client
        team = await put_in_team(db_session, user)
        challenge = await _challenge(db_session)

        resp = await c.get(
            f"/challenges/{challenge.id}", headers={"User-Agent": "curl/8.10.1"}
        )

        assert resp.status_code == 200
        [event] = await _views(db_session)
        assert event.actor_id == user.id
        assert event.target_id == challenge.id
        assert event.target_label == "Viewed"
        assert event.meta == {
            "team_id": str(team.id),
            "user_agent": "curl/8.10.1",
            "source": "cookie",
        }
        mock_redis.set.assert_any_await(
            f"{VIEWED_KEY_PREFIX}{user.id}:{challenge.id}", "1", nx=True
        )

    async def test_later_opens_are_not_recorded(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        mock_redis,
    ) -> None:
        c, _ = user_client
        mock_redis.set = AsyncMock(return_value=None)
        challenge = await _challenge(db_session)

        resp = await c.get(f"/challenges/{challenge.id}")

        assert resp.status_code == 200
        assert await _views(db_session) == []

    async def test_teamless_player_has_no_team(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, _ = user_client
        challenge = await _challenge(db_session)

        await c.get(f"/challenges/{challenge.id}")

        [event] = await _views(db_session)
        assert event.meta["team_id"] is None

    async def test_admins_are_not_recorded(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, _ = admin_client
        challenge = await _challenge(db_session)

        resp = await c.get(f"/challenges/{challenge.id}")

        assert resp.status_code == 200
        assert await _views(db_session) == []
