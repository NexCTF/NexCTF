"""Stream slots counted in Redis: limit, release and expiry."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from nexctf.core import stream_slots
from nexctf.core.config import settings
from nexctf.core.stream_slots import Share, ShareFullError


@pytest.fixture
async def share(redis: Redis) -> AsyncIterator[Share]:
    """A share of 2, removed afterwards."""
    share = Share(f"test:{uuid4().hex}", 2)
    yield share
    await redis.delete(share.key)


async def test_share_admits_up_to_its_limit(redis: Redis, share: Share) -> None:
    await stream_slots.acquire(redis, share)
    await stream_slots.acquire(redis, share)
    with pytest.raises(ShareFullError) as refused:
        await stream_slots.acquire(redis, share)
    assert refused.value.share == share


async def test_slots_are_shared_between_clients(redis: Redis, share: Share) -> None:
    """A second connection, as another worker holds, sees the same count."""
    other = Redis.from_url(str(settings.REDIS_URL), decode_responses=True)
    try:
        await stream_slots.acquire(redis, share)
        await stream_slots.acquire(other, share)
        with pytest.raises(ShareFullError):
            await stream_slots.acquire(redis, share)
    finally:
        await other.aclose()


async def test_release_frees_the_slot(redis: Redis, share: Share) -> None:
    held = [await stream_slots.acquire(redis, share) for _ in range(2)]
    await stream_slots.release(redis, held[0])
    await stream_slots.acquire(redis, share)
    assert await redis.zcard(share.key) == 2


async def test_a_slot_nobody_refreshes_expires(redis: Redis, share: Share) -> None:
    for _ in range(2):
        await stream_slots.acquire(redis, share, now=1000.0)
    later = 1000.0 + stream_slots.SLOT_TTL_SECONDS + 1
    await stream_slots.acquire(redis, share, now=later)
    assert await redis.zcard(share.key) == 1


async def test_refresh_keeps_a_slot_past_its_first_expiry(
    redis: Redis, share: Share
) -> None:
    kept = await stream_slots.acquire(redis, share, now=1000.0)
    await stream_slots.acquire(redis, share, now=1000.0)
    await stream_slots.refresh(redis, kept, now=1060.0)
    later = 1000.0 + stream_slots.SLOT_TTL_SECONDS + 1
    await stream_slots.acquire(redis, share, now=later)
    with pytest.raises(ShareFullError):
        await stream_slots.acquire(redis, share, now=later)
