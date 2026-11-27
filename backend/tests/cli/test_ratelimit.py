"""Tests for ``manager ratelimit``: live counts and clearing windows."""

import time
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from nexctf.cli.ratelimit import clear_limits, live_counts
from nexctf.core.rate_limit import rate_key

KEPT, CLEARED = "203.0.113.6", "203.0.113.7"


@pytest.fixture
async def action(redis: Redis) -> AsyncIterator[str]:
    """An action of its own, with a fresh and a stale window, deleted after."""
    name = f"test{uuid4().hex}"
    now = time.time()
    await redis.zadd(rate_key(name, KEPT), {"old": now - 120, "new": now})
    await redis.zadd(rate_key(name, CLEARED), {"old": now - 120})
    yield name
    await redis.delete(rate_key(name, KEPT), rate_key(name, CLEARED))


async def test_live_counts_skip_requests_outside_the_window(
    redis: Redis, action: str
) -> None:
    """Only requests inside the action's window are counted."""
    assert await live_counts(redis, action, None) == {KEPT: 1}


async def test_clear_limits_narrows_to_an_address(redis: Redis, action: str) -> None:
    """Clearing with an IP only deletes that address's window."""
    assert await clear_limits(redis, action, CLEARED) == 1

    assert await redis.exists(rate_key(action, KEPT))
    assert not await redis.exists(rate_key(action, CLEARED))
