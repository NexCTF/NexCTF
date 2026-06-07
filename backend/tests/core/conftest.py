"""Shared fixtures for tests/core integration tests."""

import uuid

import pytest

from nexctf.core.config import settings


@pytest.fixture
async def redis():
    """Fresh Redis client per test, bound to the test's own event loop.

    Using the module-level singleton (get_redis_client) breaks with
    pytest-asyncio's function-scoped event loops: after the first test's loop
    is closed, the pool's underlying sockets are stale and the next test raises
    'RuntimeError: Event loop is closed'.  A per-test client avoids this.
    """
    import redis.exceptions
    from redis.asyncio import Redis

    client = Redis.from_url(str(settings.REDIS_URL), decode_responses=True)
    try:
        await client.ping()
    except (redis.exceptions.ConnectionError, OSError):
        await client.aclose()
        pytest.skip(f"Redis not reachable at {settings.REDIS_URL}")
    yield client
    await client.aclose()


@pytest.fixture
async def cache_key(redis):
    """Unique Redis key that is deleted from the server after each test."""
    key = f"test:cache:{uuid.uuid4()}"
    yield key
    await redis.delete(key)


@pytest.fixture
def s3_key() -> str:
    """Unique S3 object key per test."""
    return f"test/{uuid.uuid4()}"
