from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.cache import DEFAULT_TTL, drop_keys, drop_registered, get_or_compute
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

_BOARD_REGISTRY = "scoreboard:keys:board"
_ADMIN_REGISTRY = "scoreboard:keys:admin"
_TEAM_REGISTRY = "scoreboard:keys:team"

_scoreboard_adapter: TypeAdapter[PublicScoreboard] = TypeAdapter(PublicScoreboard)
_admin_scoreboard_adapter: TypeAdapter[AdminScoreboard] = TypeAdapter(AdminScoreboard)
_team_adapter: TypeAdapter[PublicTeamScoreDetail] = TypeAdapter(PublicTeamScoreDetail)
_history_adapter: TypeAdapter[ScoreboardHistory] = TypeAdapter(ScoreboardHistory)


async def get_scoreboard(
    session: AsyncSession,
    redis: Redis,
    *,
    overrides: dict[str, str],
    bracket: str | None = None,
    ttl: timedelta = DEFAULT_TTL,
) -> PublicScoreboard:
    freeze_time = parse_config_dt("ctf.freeze_time", overrides)
    end_time = parse_config_dt("ctf.end_time", overrides)
    key = f"{_SCOREBOARD_KEY}:{bracket}" if bracket else _SCOREBOARD_KEY
    return await get_or_compute(
        redis,
        key,
        _scoreboard_adapter,
        lambda: compute_scoreboard(
            session, freeze_time=freeze_time, bracket=bracket, end_time=end_time
        ),
        ttl,
        registry=_BOARD_REGISTRY,
    )


async def get_admin_scoreboard(
    session: AsyncSession,
    redis: Redis,
    *,
    overrides: dict[str, str],
    bracket: str | None = None,
    ttl: timedelta = DEFAULT_TTL,
) -> AdminScoreboard:
    end_time = parse_config_dt("ctf.end_time", overrides)
    key = f"{_ADMIN_SCOREBOARD_KEY}:{bracket}" if bracket else _ADMIN_SCOREBOARD_KEY
    return await get_or_compute(
        redis,
        key,
        _admin_scoreboard_adapter,
        lambda: compute_admin_scoreboard(session, bracket=bracket, end_time=end_time),
        ttl,
        registry=_ADMIN_REGISTRY,
    )


async def get_team_score(
    session: AsyncSession,
    redis: Redis,
    team_id: UUID,
    *,
    overrides: dict[str, str],
    ttl: timedelta = DEFAULT_TTL,
) -> PublicTeamScoreDetail:
    freeze_time = parse_config_dt("ctf.freeze_time", overrides)
    end_time = parse_config_dt("ctf.end_time", overrides)
    return await get_or_compute(
        redis,
        f"{_TEAM_KEY_PREFIX}{team_id}",
        _team_adapter,
        lambda: compute_team_score(
            session, team_id, freeze_time=freeze_time, end_time=end_time
        ),
        ttl,
        registry=_TEAM_REGISTRY,
    )


async def get_scoreboard_history(
    session: AsyncSession,
    redis: Redis,
    *,
    overrides: dict[str, str],
    limit: int = 10,
    bracket: str | None = None,
    ttl: timedelta = DEFAULT_TTL,
) -> ScoreboardHistory:
    freeze_time = parse_config_dt("ctf.freeze_time", overrides)
    end_time = parse_config_dt("ctf.end_time", overrides)
    return await get_or_compute(
        redis,
        f"{_HISTORY_KEY}:{limit}:{bracket or '_all'}",
        _history_adapter,
        lambda: compute_scoreboard_history(
            session,
            limit=limit,
            freeze_time=freeze_time,
            bracket=bracket,
            end_time=end_time,
        ),
        ttl,
        registry=_BOARD_REGISTRY,
    )


async def invalidate(redis: Redis, team_id: UUID | None = None) -> None:
    """Invalidate the cache.

    - team_id=None  → invalidate the full scoreboard and all team caches.
    - team_id=<id>  → invalidate the scoreboard and that team's cache only.
    """
    if team_id is None:
        await drop_registered(redis, _BOARD_REGISTRY, _ADMIN_REGISTRY, _TEAM_REGISTRY)
        return

    await drop_registered(redis, _BOARD_REGISTRY, _ADMIN_REGISTRY)
    await drop_keys(redis, f"{_TEAM_KEY_PREFIX}{team_id}")


async def invalidate_play(
    redis: Redis,
    team_id: UUID | None,
    *,
    played_at: datetime,
    overrides: dict[str, str],
) -> None:
    """Drop the caches a solve or hint unlock made at *played_at* can change.

    A play after the freeze only moves the live admin board.
    """
    freeze_time = parse_config_dt("ctf.freeze_time", overrides)
    if freeze_time is not None and played_at > freeze_time:
        await drop_registered(redis, _ADMIN_REGISTRY)
        return
    await invalidate(redis, team_id)
