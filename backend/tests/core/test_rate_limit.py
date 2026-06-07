"""Integration tests for nexctf.core.rate_limit (real Redis, sliding window)."""

import pytest
from fastapi import HTTPException

from nexctf.core.rate_limit import check_rate_limit


async def test_allows_requests_under_limit(redis):
    key = "test:rl:under"
    for _ in range(3):
        await check_rate_limit(redis, key, window_seconds=10, max_requests=3)


async def test_blocks_when_limit_exceeded(redis):
    key = "test:rl:exceed"
    for _ in range(5):
        await check_rate_limit(redis, key, window_seconds=10, max_requests=5)

    with pytest.raises(HTTPException) as exc_info:
        await check_rate_limit(redis, key, window_seconds=10, max_requests=5)

    assert exc_info.value.status_code == 429


async def test_independent_keys_do_not_share_counts(redis):
    for _ in range(3):
        await check_rate_limit(redis, "test:rl:keyA", window_seconds=10, max_requests=3)

    # keyB starts fresh — should not be affected by keyA usage
    await check_rate_limit(redis, "test:rl:keyB", window_seconds=10, max_requests=1)
