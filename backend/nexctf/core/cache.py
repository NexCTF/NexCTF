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
_VERSION_TTL_SECONDS = 86_400
_STORE_IF_CURRENT = """
local versions = #ARGV - 2
for i = 1, versions do
    if (redis.call('GET', KEYS[i + 1]) or '0') ~= ARGV[i + 2] then
        return 0
    end
end
redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
if KEYS[versions + 2] then
    redis.call('SADD', KEYS[versions + 2], KEYS[1])
end
return 1
"""


def _lock_key(key: str) -> str:
    """Key held while one request computes *key*."""
    return f"{key}:computing"


def _scopes(key: str, registry: str | None) -> list[str]:
    """The names whose invalidation makes a compute of *key* stale."""
    return [key] if registry is None else [key, registry]


def _version_key(name: str) -> str:
    """Key counting the invalidations of the cache key or registry *name*."""
    return f"{name}:version"


async def _versions(redis: Redis, names: list[str]) -> list[str | bytes]:
    """Current invalidation counts of *names*, "0" for those never invalidated."""
    values = await redis.mget([_version_key(n) for n in names])
    return [v or "0" for v in values]


async def _store_if_current(
    redis: Redis,
    key: str,
    payload: bytes,
    ttl: timedelta,
    registry: str | None,
    versions: list[str | bytes],
) -> None:
    """Cache *payload* unless *key* or its registry was invalidated since *versions*."""
    keys = [
        key,
        *(_version_key(n) for n in _scopes(key, registry)),
        *([registry] if registry is not None else []),
    ]
    ttl_ms = int(ttl.total_seconds() * 1000)
    await cast(
        Any,
        redis.eval(_STORE_IF_CURRENT, len(keys), *keys, payload, ttl_ms, *versions),
    )


async def _bump_versions(redis: Redis, names: tuple[str, ...]) -> None:
    """Mark *names* as invalidated, so computes already running do not store."""
    pipe = redis.pipeline()
    for name in names:
        pipe.incr(_version_key(name))
        pipe.expire(_version_key(name), _VERSION_TTL_SECONDS)
    await pipe.execute()


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
    """Poll *key* while another request computes it.

    Gives up when that request stops without storing, or after a while.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _COMPUTE_WAIT_SECONDS
    while loop.time() < deadline:
        await asyncio.sleep(_COMPUTE_POLL_SECONDS)
        value = await _load(redis, key, adapter)
        if not isinstance(value, _Miss):
            return value
        if not await redis.exists(_lock_key(key)):
            return _MISS
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

    lock_key = _lock_key(key)
    token = secrets.token_hex(8)
    held = bool(await redis.set(lock_key, token, nx=True, px=_COMPUTE_LOCK_TTL_MS))
    if not held:
        cached = await _wait_for(redis, key, adapter)
        if not isinstance(cached, _Miss):
            return cached

    versions = await _versions(redis, _scopes(key, registry))
    try:
        result = await compute()
        await _store_if_current(
            redis, key, adapter.dump_json(result), ttl, registry, versions
        )
    finally:
        if held:
            await cast(Any, redis.eval(_RELEASE_IF_HELD, 1, lock_key, token))
    return result


async def drop_registered(redis: Redis, *registries: str) -> None:
    """Delete every key recorded in *registries*, then the registries themselves."""
    await _bump_versions(redis, registries)
    keys = await redis.sunion(list(registries))
    await redis.delete(*keys, *registries)


async def drop_keys(redis: Redis, *keys: str) -> None:
    """Delete the cache *keys*, keeping computes already running from storing them."""
    await _bump_versions(redis, keys)
    await redis.delete(*keys)
