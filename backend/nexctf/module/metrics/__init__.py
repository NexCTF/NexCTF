"""Prometheus metric families, built fresh on every scrape."""

from __future__ import annotations

from prometheus_client.core import Metric
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core import appconfig

from .build import build_metrics
from .competition import competition_metrics
from .counters import counter_metrics
from .domain import domain_metrics
from .queue import queue_metrics


async def collect_metrics(session: AsyncSession, redis: Redis) -> list[Metric]:
    """Every NexCTF metric family, read now."""
    overrides = await appconfig.fetch_overrides(redis)
    return [
        *build_metrics(),
        *competition_metrics(overrides),
        *await domain_metrics(session, redis),
        *await queue_metrics(session),
        *await counter_metrics(redis),
    ]


__all__ = ["collect_metrics"]
