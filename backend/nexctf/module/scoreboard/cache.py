from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.cache import DEFAULT_TTL, get_or_compute
from nexctf.module.scoreboard.compute import (
    compute_admin_scoreboard,
    compute_scoreboard,
    compute_scoreboard_history,
    compute_team_score,
)
from nexctf.schema import (
    AdminScoreboard,
    PublicScoreboard,
    PublicTeamScoreDetail,
    ScoreboardHistory,
)
from nexctf.util.datetime import parse_config_dt

_SCOREBOARD_KEY = "scoreboard:full"
_ADMIN_SCOREBOARD_KEY = "scoreboard:admin:full"
_TEAM_KEY_PREFIX = "scoreboard:team:"
_HISTORY_KEY = "scoreboard:history"

_scoreboard_adapter: TypeAdapter[PublicScoreboard] = TypeAdapter(PublicScoreboard)
_admin_scoreboard_adapter: TypeAdapter[AdminScoreboard] = TypeAdapter(AdminScoreboard)
_team_adapter: TypeAdapter[PublicTeamScoreDetail] = TypeAdapter(PublicTeamScoreDetail)
_history_adapter: TypeAdapter[ScoreboardHistory] = TypeAdapter(ScoreboardHistory)


async def get_scoreboard(
    session: AsyncSession,
    redis: Redis,
    ttl: timedelta = DEFAULT_TTL,
) -> PublicScoreboard:
    freeze_time = parse_config_dt("ctf.freeze_time")
    return await get_or_compute(
        redis,
        _SCOREBOARD_KEY,
        _scoreboard_adapter,
        lambda: compute_scoreboard(session, freeze_time=freeze_time),
        ttl,
    )


async def get_admin_scoreboard(
    session: AsyncSession,
    redis: Redis,
    ttl: timedelta = DEFAULT_TTL,
) -> AdminScoreboard:
    return await get_or_compute(
        redis,
        _ADMIN_SCOREBOARD_KEY,
        _admin_scoreboard_adapter,
        lambda: compute_admin_scoreboard(session),
        ttl,
    )


async def get_team_score(
    session: AsyncSession,
    redis: Redis,
    team_id: UUID,
    ttl: timedelta = DEFAULT_TTL,
) -> PublicTeamScoreDetail:
    freeze_time = parse_config_dt("ctf.freeze_time")
    return await get_or_compute(
        redis,
        f"{_TEAM_KEY_PREFIX}{team_id}",
        _team_adapter,
        lambda: compute_team_score(session, team_id, freeze_time=freeze_time),
        ttl,
    )


async def get_scoreboard_history(
    session: AsyncSession,
    redis: Redis,
    limit: int = 10,
    ttl: timedelta = DEFAULT_TTL,
) -> ScoreboardHistory:
    freeze_time = parse_config_dt("ctf.freeze_time")
    return await get_or_compute(
        redis,
        f"{_HISTORY_KEY}:{limit}",
        _history_adapter,
        lambda: compute_scoreboard_history(
            session, limit=limit, freeze_time=freeze_time
        ),
        ttl,
    )


async def invalidate(redis: Redis, team_id: UUID | None = None) -> None:
    """Invalidate the cache.

    - team_id=None  → invalidate the full scoreboard and all team caches.
    - team_id=<id>  → invalidate the scoreboard and that team's cache only.
    """
    keys: list[str] = [_SCOREBOARD_KEY, _ADMIN_SCOREBOARD_KEY]

    if team_id is None:
        async for key in redis.scan_iter(f"{_TEAM_KEY_PREFIX}*"):
            keys.append(key)
        async for key in redis.scan_iter(f"{_HISTORY_KEY}:*"):
            keys.append(key)
    else:
        keys.append(f"{_TEAM_KEY_PREFIX}{team_id}")
        async for key in redis.scan_iter(f"{_HISTORY_KEY}:*"):
            keys.append(key)

    await redis.delete(*keys)
