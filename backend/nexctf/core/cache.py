"""Redis client setup and generic cache helper."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import timedelta
from typing import TypeVar

from pydantic import TypeAdapter
from redis.asyncio import Redis

from nexctf.core.config import settings

T = TypeVar("T")

DEFAULT_TTL = timedelta(seconds=30)

_client: Redis | None = None


def get_client() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(
            str(settings.REDIS_URL),
            decode_responses=True,
            health_check_interval=30,
        )
    return _client


async def get_redis() -> AsyncGenerator[Redis, None]:
    yield get_client()


async def get_or_compute(
    redis: Redis,
    key: str,
    adapter: TypeAdapter[T],
    compute: Callable[[], Awaitable[T]],
    ttl: timedelta = DEFAULT_TTL,
) -> T:
    """Return a cached value, recomputing and storing it when the key is absent or expired.

    Args:
        redis:   Redis client.
        key:     Cache key.
        adapter: Pydantic TypeAdapter used for JSON serialisation / deserialisation.
        compute: Async callable that produces a fresh value when the cache is cold.
        ttl:     How long to keep the cached value.
    """
    raw = await redis.get(key)
    if raw:
        return adapter.validate_json(raw)
    result = await compute()
    await redis.setex(key, int(ttl.total_seconds()), adapter.dump_json(result))
    return result
