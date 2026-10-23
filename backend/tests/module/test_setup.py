"""Tests for the first-run setup token and the admin gate."""

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import UserRole
from nexctf.module.setup import (
    admin_exists,
    consume_setup_token,
    issue_setup_token,
    refresh_setup_token,
    setup_token_matches,
)
from tests.base import make_user

pytestmark = pytest.mark.usefixtures("setup_key")


async def test_only_the_issued_token_matches(redis: Redis, setup_key: str) -> None:
    token = await issue_setup_token(redis)

    assert await setup_token_matches(redis, token)
    assert not await setup_token_matches(redis, token[:-1])
    assert await redis.get(setup_key) != token


async def test_a_new_token_replaces_the_previous(redis: Redis) -> None:
    first = await issue_setup_token(redis)
    second = await issue_setup_token(redis)

    assert not await setup_token_matches(redis, first)
    assert await setup_token_matches(redis, second)


async def test_consume_succeeds_once(redis: Redis) -> None:
    token = await issue_setup_token(redis)

    assert await consume_setup_token(redis)
    assert not await consume_setup_token(redis)
    assert not await setup_token_matches(redis, token)


@pytest.mark.parametrize(
    ("roles", "expected"),
    [((), False), ((UserRole.user,), False), ((UserRole.user, UserRole.admin), True)],
)
async def test_admin_exists(
    db_session: AsyncSession, roles: tuple[UserRole, ...], expected: bool
) -> None:
    for i, role in enumerate(roles):
        await make_user(db_session, f"u{i}", role=role)

    assert await admin_exists(db_session) is expected


async def test_refresh_issues_a_token_while_no_admin_exists(
    db_session: AsyncSession, redis: Redis
) -> None:
    await make_user(db_session, "player")

    token = await refresh_setup_token(db_session, redis)

    assert token is not None
    assert await setup_token_matches(redis, token)


async def test_refresh_drops_the_token_once_an_admin_exists(
    db_session: AsyncSession, redis: Redis
) -> None:
    stale = await issue_setup_token(redis)
    await make_user(db_session, "root", role=UserRole.admin)

    assert await refresh_setup_token(db_session, redis) is None
    assert not await setup_token_matches(redis, stale)
