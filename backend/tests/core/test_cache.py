"""Integration tests for nexctf.core.cache.get_or_compute (real Redis)."""

from datetime import timedelta
from unittest.mock import AsyncMock

from pydantic import TypeAdapter

from nexctf.core.cache import DEFAULT_TTL, drop_registered, get_or_compute


async def test_cache_miss_calls_compute_and_stores(redis, cache_key):
    adapter = TypeAdapter(str)
    compute = AsyncMock(return_value="hello")

    result = await get_or_compute(
        redis, cache_key, adapter, compute, timedelta(seconds=5)
    )

    assert result == "hello"
    compute.assert_awaited_once()
    stored = await redis.get(cache_key)
    assert adapter.validate_json(stored) == "hello"


async def test_cache_hit_returns_cached_and_skips_compute(redis, cache_key):
    adapter = TypeAdapter(str)
    await redis.set(cache_key, adapter.dump_json("from-cache"))
    compute = AsyncMock()

    result = await get_or_compute(redis, cache_key, adapter, compute)

    assert result == "from-cache"
    compute.assert_not_awaited()


async def test_ttl_is_applied(redis, cache_key):
    adapter = TypeAdapter(int)
    await get_or_compute(
        redis, cache_key, adapter, AsyncMock(return_value=42), timedelta(seconds=30)
    )

    ttl = await redis.ttl(cache_key)
    assert 25 <= ttl <= 30


async def test_default_ttl_matches_constant(redis, cache_key):
    adapter = TypeAdapter(str)
    await get_or_compute(redis, cache_key, adapter, AsyncMock(return_value="x"))

    ttl = await redis.ttl(cache_key)
    expected = int(DEFAULT_TTL.total_seconds())
    assert expected - 5 <= ttl <= expected


async def test_complex_type_round_trips_through_cache(redis, cache_key):
    adapter = TypeAdapter(list[dict[str, int]])
    value = [{"a": 1}, {"b": 2}]

    result = await get_or_compute(
        redis, cache_key, adapter, AsyncMock(return_value=value)
    )
    assert result == value

    second = await get_or_compute(redis, cache_key, adapter, AsyncMock())
    assert second == value


async def test_drop_registered_clears_the_registered_group(redis, cache_key):
    """drop_registered deletes every registered key and the registry itself."""
    adapter = TypeAdapter(str)
    registry, second = f"{cache_key}:registry", f"{cache_key}:second"
    expired = f"{cache_key}:already-gone"

    await get_or_compute(
        redis, cache_key, adapter, AsyncMock(return_value="a"), registry=registry
    )
    await get_or_compute(
        redis, second, adapter, AsyncMock(return_value="b"), registry=registry
    )
    await redis.sadd(registry, expired)
    assert await redis.smembers(registry) == {cache_key, second, expired}

    await drop_registered(redis, registry)

    assert await redis.get(cache_key) is None
    assert await redis.get(second) is None
    assert await redis.exists(registry) == 0


async def test_stale_payload_is_recomputed(redis, cache_key):
    """A cached payload that no longer matches the schema must not raise."""
    adapter = TypeAdapter(dict[str, int])
    await redis.set(cache_key, b'{"old_field": "not-an-int"}')
    compute = AsyncMock(return_value={"n": 1})

    result = await get_or_compute(redis, cache_key, adapter, compute)

    assert result == {"n": 1}
    compute.assert_awaited_once()
    assert adapter.validate_json(await redis.get(cache_key)) == {"n": 1}
