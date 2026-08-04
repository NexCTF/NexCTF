"""Redis client setup and generic cache helper."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import timedelta

from pydantic import TypeAdapter, ValidationError
from redis.asyncio import Redis

from nexctf.core.config import settings

logger = logging.getLogger(__name__)

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


async def get_redis() -> AsyncGenerator[Redis]:
    yield get_client()


async def get_or_compute[T](
    redis: Redis,
    key: str,
    adapter: TypeAdapter[T],
    compute: Callable[[], Awaitable[T]],
    ttl: timedelta = DEFAULT_TTL,
    registry: str | None = None,
) -> T:
    """Return a cached value, recomputing and storing it when the key is absent or expired.

    Args:
        redis:   Redis client.
        key:     Cache key.
        adapter: Pydantic TypeAdapter used for JSON serialisation / deserialisation.
        compute: Async callable that produces a fresh value when the cache is cold.
        ttl:     How long to keep the cached value.
        registry: Set that records *key* for drop_registered.
    """
    raw = await redis.get(key)
    if raw:
        try:
            return adapter.validate_json(raw)
        except ValidationError:
            logger.info("cache.stale_payload key=%s", key)
    result = await compute()
    pipe = redis.pipeline()
    pipe.setex(key, int(ttl.total_seconds()), adapter.dump_json(result))
    if registry is not None:
        pipe.sadd(registry, key)
    await pipe.execute()
    return result


async def drop_registered(redis: Redis, *registries: str) -> None:
    """Delete every key recorded in *registries*, then the registries themselves."""
    keys = await redis.sunion(list(registries))
    await redis.delete(*keys, *registries)
