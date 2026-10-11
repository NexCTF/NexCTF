"""Event counters shared by every worker, kept in one Redis hash."""

from __future__ import annotations

import logging
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from nexctf.core.config import settings

logger = logging.getLogger(__name__)

_KEY = "metrics:counters"


async def incr_counter(redis: Redis, name: str, value: str) -> None:
    """Add one to counter ``name`` for label ``value``; no-op when metrics are off."""
    if not settings.metrics_served:
        return
    try:
        await redis.hincrby(_KEY, f"{name}:{value}", 1)
    except RedisError:
        logger.warning("could not increment metric counter %s", name, exc_info=True)


async def read_counters(redis: Redis) -> dict[str, dict[str, int]]:
    """Every counter's value per label, keyed by counter name."""
    counters: dict[str, dict[str, int]] = {}
    fields = cast(dict[str, str], await redis.hgetall(_KEY))
    for field, count in fields.items():
        name, _, value = field.partition(":")
        counters.setdefault(name, {})[value] = int(count)
    return counters
