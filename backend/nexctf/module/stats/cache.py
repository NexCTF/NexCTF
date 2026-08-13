from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.cache import drop_registered, get_or_compute
from nexctf.module.stats.compute import (
    compute_all_challenge_stats,
    compute_team_challenge_stats,
)
from nexctf.schema.stats import ChallengeStats, TeamChallengeStats
from nexctf.util.datetime import is_config_dt_past, parse_config_dt

_KEY = "stats:challenges"
_TEAM_KEY_PREFIX = "stats:team:"
_TEAM_REGISTRY = "stats:keys:team"
_TTL = timedelta(seconds=60)


_adapter: TypeAdapter[list[ChallengeStats]] = TypeAdapter(list[ChallengeStats])
_team_adapter: TypeAdapter[list[TeamChallengeStats]] = TypeAdapter(
    list[TeamChallengeStats]
)


def _team_key(team_id: UUID, frozen: bool = False) -> str:
    """Cache key for a team's stats, live or frozen."""
    return f"{_TEAM_KEY_PREFIX}{team_id}{':frozen' if frozen else ''}"


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
    *,
    overrides: dict[str, str],
    live: bool = False,
    ttl: timedelta = _TTL,
) -> list[TeamChallengeStats]:
    """Return a team's cached per-challenge progress, frozen unless live=True."""
    frozen = not live and is_config_dt_past("ctf.freeze_time", overrides)
    freeze_time = parse_config_dt("ctf.freeze_time", overrides) if frozen else None
    return await get_or_compute(
        redis,
        _team_key(team_id, frozen),
        _team_adapter,
        lambda: compute_team_challenge_stats(session, team_id, freeze_time=freeze_time),
        ttl,
        registry=_TEAM_REGISTRY,
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
        await drop_registered(redis, _TEAM_REGISTRY)
        return

    await redis.delete(_team_key(team_id), _team_key(team_id, frozen=True))
