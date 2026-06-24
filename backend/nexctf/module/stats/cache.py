from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.cache import get_or_compute
from nexctf.module.stats.compute import (
    compute_all_challenge_stats,
    compute_team_challenge_stats,
)
from nexctf.schema.stats import ChallengeStats, TeamChallengeStats

_KEY = "stats:challenges"
_TEAM_KEY_PREFIX = "stats:team:"
_TTL = timedelta(seconds=60)

_adapter: TypeAdapter[list[ChallengeStats]] = TypeAdapter(list[ChallengeStats])
_team_adapter: TypeAdapter[list[TeamChallengeStats]] = TypeAdapter(
    list[TeamChallengeStats]
)


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


async def get_team_challenge_stats(
    session: AsyncSession,
    redis: Redis,
    team_id: UUID,
    ttl: timedelta = _TTL,
) -> list[TeamChallengeStats]:
    """Return a team's cached per-challenge progress, recomputing when cold."""
    return await get_or_compute(
        redis,
        f"{_TEAM_KEY_PREFIX}{team_id}",
        _team_adapter,
        lambda: compute_team_challenge_stats(session, team_id),
        ttl,
    )


async def invalidate(redis: Redis) -> None:
    """Drop the cached challenge stats so the next request recomputes them."""
    await redis.delete(_KEY)


async def invalidate_team(redis: Redis, team_id: UUID | None = None) -> None:
    """Drop cached per-team challenge stats.

    - team_id=None  → invalidate every team's cached stats.
    - team_id=<id>  → invalidate that team's cached stats only.
    """
    if team_id is None:
        keys = [key async for key in redis.scan_iter(f"{_TEAM_KEY_PREFIX}*")]
        if keys:
            await redis.delete(*keys)
    else:
        await redis.delete(f"{_TEAM_KEY_PREFIX}{team_id}")
