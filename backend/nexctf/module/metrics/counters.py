"""Event counters read back from Redis."""

from __future__ import annotations

from prometheus_client.core import CounterMetricFamily, Metric
from redis.asyncio import Redis

from nexctf.core.metrics import read_counters

_COUNTERS = {
    "rate_limited": ("Requests rejected by a rate limit.", "limit"),
    "captcha_failures": ("Rejected captcha answers.", "reason"),
    "emails": ("Emails by delivery outcome.", "result"),
}


async def counter_metrics(redis: Redis) -> list[Metric]:
    """Every event counter, including those never incremented yet."""
    counters = await read_counters(redis)
    families: list[Metric] = []
    for name, (documentation, label) in _COUNTERS.items():
        family = CounterMetricFamily(f"nexctf_{name}", documentation, labels=[label])
        for value, count in sorted(counters.get(name, {}).items()):
            family.add_metric([value], count)
        families.append(family)
    return families
