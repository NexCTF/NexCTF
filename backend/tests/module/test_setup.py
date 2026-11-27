"""Tests for the first-run setup token and the admin gate."""

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import UserRole
from nexctf.module import setup
from nexctf.module.setup import (
    admin_exists,
    consume_setup_token,
    issue_setup_token,
    setup_done,
    setup_token_matches,
)
from tests.base import make_user

pytestmark = pytest.mark.usefixtures("setup_key")


@pytest.fixture
async def setup_key(
    redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[str]:
    """Point the setup token at a key of its own, deleted after the test."""
    key = f"test:setup:{uuid.uuid4()}"
    monkeypatch.setattr(setup, "SETUP_TOKEN_KEY", key)
    yield key
    await redis.delete(key)


async def test_only_the_issued_token_matches(redis: Redis, setup_key: str) -> None:
    token = await issue_setup_token(redis, replace=True)

    assert token is not None
    assert await setup_token_matches(redis, token)
    assert not await setup_token_matches(redis, token[:-1])
    assert await redis.get(setup_key) != token


async def test_an_issued_token_is_kept_unless_replaced(redis: Redis) -> None:
    first = await issue_setup_token(redis, replace=False)
    assert first is not None
    assert await issue_setup_token(redis, replace=False) is None
    assert await setup_token_matches(redis, first)

    second = await issue_setup_token(redis, replace=True)

    assert second is not None
    assert not await setup_token_matches(redis, first)
    assert await setup_token_matches(redis, second)


async def test_consume_succeeds_once(redis: Redis) -> None:
    token = await issue_setup_token(redis, replace=True)
    assert token is not None

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


@pytest.fixture
async def done_key(
    redis: Redis, override_db_context: None, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[str]:
    """A fresh process with its own done flag, reading the test database."""
    key = f"test:setup-done:{uuid.uuid4()}"
    monkeypatch.setattr(setup, "SETUP_DONE_KEY", key)
    monkeypatch.setattr(setup, "_admin_seen", False)
    yield key
    await redis.delete(key)


async def test_setup_done_once_an_admin_is_seen(
    db_session: AsyncSession, redis: Redis, done_key: str
) -> None:
    """The first admin found is shared through Redis for the other workers."""
    assert not await setup_done(redis)
    assert not await redis.exists(done_key)

    await make_user(db_session, "root", role=UserRole.admin)

    assert await setup_done(redis)
    assert await redis.exists(done_key)


async def test_setup_stays_done_for_new_workers(
    redis: Redis, done_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker started after the flag was set never reopens the gate."""
    await redis.set(done_key, "1")

    @asynccontextmanager
    async def _no_db() -> AsyncGenerator[AsyncSession]:
        raise AssertionError("the database should not be read")
        yield

    monkeypatch.setattr(setup, "get_db_context", _no_db)

    assert await setup_done(redis)
