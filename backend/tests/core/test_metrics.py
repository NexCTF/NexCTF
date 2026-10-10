"""Redis-backed event counters and the event phase."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from nexctf.core.config import settings
from nexctf.core.metrics import incr_counter, read_counters
from nexctf.core.rate_limit import check_rate_limit
from nexctf.module.metrics.competition import _phase


@pytest.fixture
def metrics_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve metrics whatever the environment."""
    monkeypatch.setattr(settings, "METRICS_TOKEN", "t")


async def test_incr_counter_is_off_without_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "METRICS_ENABLED", False)
    redis = AsyncMock()
    await incr_counter(redis, "emails", "sent")
    redis.hincrby.assert_not_called()


@pytest.mark.usefixtures("metrics_on")
async def test_counters_round_trip() -> None:
    store: dict[str, int] = {}

    async def hincrby(key: str, field: str, amount: int) -> None:
        store[field] = store.get(field, 0) + amount

    redis = AsyncMock()
    redis.hincrby = hincrby
    redis.hgetall = AsyncMock(return_value=store)

    await incr_counter(redis, "emails", "sent")
    await incr_counter(redis, "emails", "sent")
    await incr_counter(redis, "emails", "failed")

    assert await read_counters(redis) == {"emails": {"sent": 2, "failed": 1}}


@pytest.mark.usefixtures("metrics_on")
async def test_incr_counter_survives_redis_errors() -> None:
    redis = AsyncMock()
    redis.hincrby = AsyncMock(side_effect=RedisConnectionError())
    await incr_counter(redis, "emails", "sent")


@pytest.mark.usefixtures("metrics_on")
async def test_rejected_rate_limit_counts_its_name() -> None:
    pipeline = MagicMock()
    pipeline.execute = AsyncMock(return_value=[None, None, 2, None])
    redis = AsyncMock()
    redis.pipeline = MagicMock(return_value=pipeline)

    with pytest.raises(HTTPException):
        await check_rate_limit(
            redis, "rl:x:y", name="submit", window_seconds=60, max_requests=1
        )

    redis.hincrby.assert_awaited_once_with("metrics:counters", "rate_limited:submit", 1)


def _times(**offsets: int) -> dict[str, datetime | None]:
    now = datetime.now(UTC)
    return {
        name: now + timedelta(hours=offsets[name]) if name in offsets else None
        for name in ("start", "end", "freeze")
    }


@pytest.mark.parametrize(
    ("offsets", "phase"),
    [
        ({}, "running"),
        ({"start": 1}, "not_started"),
        ({"start": -1, "end": 1}, "running"),
        ({"start": -2, "freeze": -1, "end": 1}, "frozen"),
        ({"start": -3, "freeze": -2, "end": -1}, "ended"),
    ],
)
def test_phase(offsets: dict[str, int], phase: str) -> None:
    assert _phase(_times(**offsets)) == phase
