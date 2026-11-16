"""Integration tests for nexctf.core.rate_limit (real Redis, sliding window)."""

from uuid import uuid4

import pytest

from nexctf.core.rate_limit import (
    USER_WRITE_MAX_REQUESTS,
    check_failure_limit,
    check_rate_limit,
    check_user_write_limit,
    record_failure,
)
from nexctf.exceptions import RateLimitedError


async def test_allows_requests_under_limit(redis):
    key = "test:rl:under"
    for _ in range(3):
        await check_rate_limit(redis, key, window_seconds=10, max_requests=3)


async def test_blocks_when_limit_exceeded(redis):
    key = "test:rl:exceed"
    for _ in range(5):
        await check_rate_limit(redis, key, window_seconds=10, max_requests=5)

    with pytest.raises(RateLimitedError):
        await check_rate_limit(redis, key, window_seconds=10, max_requests=5)


async def test_independent_keys_do_not_share_counts(redis):
    for _ in range(3):
        await check_rate_limit(redis, "test:rl:keyA", window_seconds=10, max_requests=3)

    # keyB starts fresh — should not be affected by keyA usage
    await check_rate_limit(redis, "test:rl:keyB", window_seconds=10, max_requests=1)


async def test_refused_requests_do_not_extend_the_window(redis):
    key = "test:rl:retry"
    await redis.delete(key)
    await check_rate_limit(redis, key, window_seconds=10, max_requests=1)
    for _ in range(3):
        with pytest.raises(RateLimitedError):
            await check_rate_limit(redis, key, window_seconds=10, max_requests=1)

    assert await redis.zcard(key) == 1


async def test_failure_limit_counts_only_recorded_failures(redis):
    key = "test:rl:failures"
    await redis.delete(key)
    limit = {"window_seconds": 10, "max_failures": 2, "name": "test"}
    await check_failure_limit(redis, key, **limit)
    await check_failure_limit(redis, key, **limit)
    await record_failure(redis, key, window_seconds=10)
    await record_failure(redis, key, window_seconds=10)

    with pytest.raises(RateLimitedError):
        await check_failure_limit(redis, key, **limit)


async def test_user_write_limit_is_per_user_and_per_family(redis):
    user, other = uuid4(), uuid4()
    for _ in range(USER_WRITE_MAX_REQUESTS):
        await check_user_write_limit(redis, user, "test_write")

    with pytest.raises(RateLimitedError):
        await check_user_write_limit(redis, user, "test_write")
    await check_user_write_limit(redis, other, "test_write")
    await check_user_write_limit(redis, user, "test_other")
    await redis.delete(
        f"rl:test_write:{user}", f"rl:test_write:{other}", f"rl:test_other:{user}"
    )
