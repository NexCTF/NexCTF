"""Tests for the team row lock a submit holds against a concurrent leave."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nexctf.exceptions import NoTeamError, TeamDisqualifiedError
from nexctf.model import Team, User
from nexctf.module.team import lock_membership, lock_playing_team


@pytest.fixture
async def members(
    db_session: AsyncSession, sessions: async_sessionmaker
) -> AsyncIterator[tuple[User, User]]:
    """Two committed teammates, removed with their team afterwards.

    Depends on ``db_session`` for the schema it creates.
    """
    tag = uuid4().hex[:12]
    async with sessions() as session:
        team = Team(name=f"lock-{tag}", invite_code=tag.upper())
        session.add(team)
        await session.flush()
        users = [
            User(username=f"lock-{tag}-{i}", hashed_password="x", team_id=team.id)
            for i in range(2)
        ]
        session.add_all(users)
        await session.commit()
    try:
        yield users[0], users[1]
    finally:
        async with sessions() as session:
            await session.execute(
                delete(User).where(User.id.in_([u.id for u in users]))
            )
            await session.execute(delete(Team).where(Team.id == team.id))
            await session.commit()


async def _leaving(session: AsyncSession, user: User) -> None:
    """Take the row locks ``leave_team`` takes, giving up after 200ms."""
    await session.execute(text("SET LOCAL lock_timeout = '200ms'"))
    team_id = await lock_membership(session, user)
    await session.execute(select(Team.id).where(Team.id == team_id).with_for_update())


@pytest.mark.parametrize("leaver", [0, 1], ids=["submitter", "teammate"])
async def test_leave_waits_for_a_submit(
    sessions: async_sessionmaker, members: tuple[User, User], leaver: int
) -> None:
    async with sessions() as submit, sessions() as leave:
        await lock_playing_team(submit, members[0])
        with pytest.raises(DBAPIError):
            await _leaving(leave, members[leaver])


async def test_teammates_submit_together(
    sessions: async_sessionmaker, members: tuple[User, User]
) -> None:
    first, second = members
    async with sessions() as one, sessions() as two:
        await lock_playing_team(one, first)
        await two.execute(text("SET LOCAL lock_timeout = '200ms'"))
        await lock_playing_team(two, second)


async def test_a_member_who_left_is_refused(
    sessions: async_sessionmaker, members: tuple[User, User]
) -> None:
    submitter, _ = members
    async with sessions() as session:
        row = await session.get(User, submitter.id)
        assert row is not None
        row.team_id = None
        await session.commit()
    async with sessions() as session:
        with pytest.raises(NoTeamError):
            await lock_playing_team(session, submitter)


async def test_a_disqualified_team_is_refused(
    sessions: async_sessionmaker, members: tuple[User, User]
) -> None:
    submitter, _ = members
    async with sessions() as session:
        team = await session.get(Team, submitter.team_id)
        assert team is not None
        team.is_disqualified = True
        await session.commit()
    async with sessions() as session:
        with pytest.raises(TeamDisqualifiedError):
            await lock_playing_team(session, submitter)
