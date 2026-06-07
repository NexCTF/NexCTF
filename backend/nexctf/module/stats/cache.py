from __future__ import annotations

from datetime import timedelta

from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.cache import get_or_compute
from nexctf.module.stats.compute import compute_all_challenge_stats
from nexctf.schema.stats import ChallengeStats

_KEY = "stats:challenges"
_TTL = timedelta(seconds=60)

_adapter: TypeAdapter[list[ChallengeStats]] = TypeAdapter(list[ChallengeStats])


async def get_all_challenge_stats(
    session: AsyncSession,
    redis: Redis,
    ttl: timedelta = _TTL,
) -> list[ChallengeStats]:
    return await get_or_compute(
        redis,
        _KEY,
        _adapter,
        lambda: compute_all_challenge_stats(session),
        ttl,
    )


async def invalidate(redis: Redis) -> None:
    """Drop the cached challenge stats so the next request recomputes them."""
    await redis.delete(_KEY)
