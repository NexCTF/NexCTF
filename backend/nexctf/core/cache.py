"""Redis client setup and generic cache helper."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import timedelta
from typing import Any, cast

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


class _Miss:
    """Marks a key that holds no usable cached value."""


_MISS = _Miss()
_COMPUTE_LOCK_TTL_MS = 10_000
_COMPUTE_WAIT_SECONDS = 2.0
_COMPUTE_POLL_SECONDS = 0.05
_RELEASE_IF_HELD = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


async def _load[T](redis: Redis, key: str, adapter: TypeAdapter[T]) -> T | _Miss:
    """Return the cached value at *key*, or _MISS when absent or stale."""
    raw = await redis.get(key)
    if raw:
        try:
            return adapter.validate_json(raw)
        except ValidationError:
            logger.info("cache.stale_payload key=%s", key)
    return _MISS


async def _wait_for[T](redis: Redis, key: str, adapter: TypeAdapter[T]) -> T | _Miss:
    """Poll *key* while another request computes it, giving up after a while."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _COMPUTE_WAIT_SECONDS
    while loop.time() < deadline:
        await asyncio.sleep(_COMPUTE_POLL_SECONDS)
        value = await _load(redis, key, adapter)
        if not isinstance(value, _Miss):
            return value
    return _MISS


async def get_or_compute[T](
    redis: Redis,
    key: str,
    adapter: TypeAdapter[T],
    compute: Callable[[], Awaitable[T]],
    ttl: timedelta = DEFAULT_TTL,
    registry: str | None = None,
) -> T:
    """Return a cached value, recomputing and storing it when the key is absent or expired.

    Concurrent misses compute once: the first takes a lock, the others wait for
    its result and only compute themselves if it takes too long.

    Args:
        redis:   Redis client.
        key:     Cache key.
        adapter: Pydantic TypeAdapter used for JSON serialisation / deserialisation.
        compute: Async callable that produces a fresh value when the cache is cold.
        ttl:     How long to keep the cached value.
        registry: Set that records *key* for drop_registered.
    """
    cached = await _load(redis, key, adapter)
    if not isinstance(cached, _Miss):
        return cached

    lock_key = f"{key}:computing"
    token = secrets.token_hex(8)
    held = bool(await redis.set(lock_key, token, nx=True, px=_COMPUTE_LOCK_TTL_MS))
    if not held:
        cached = await _wait_for(redis, key, adapter)
        if not isinstance(cached, _Miss):
            return cached

    try:
        result = await compute()
        pipe = redis.pipeline()
        pipe.set(key, adapter.dump_json(result), ex=ttl)
        if registry is not None:
            pipe.sadd(registry, key)
        await pipe.execute()
    finally:
        if held:
            await cast(Any, redis.eval(_RELEASE_IF_HELD, 1, lock_key, token))
    return result


async def drop_registered(redis: Redis, *registries: str) -> None:
    """Delete every key recorded in *registries*, then the registries themselves."""
    keys = await redis.sunion(list(registries))
    await redis.delete(*keys, *registries)
