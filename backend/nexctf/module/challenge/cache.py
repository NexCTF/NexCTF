"""Redis caching for the user-agnostic challenge structures."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.cache import get_or_compute
from nexctf.module.challenge.compute import (
    ChallengeDetailStructure,
    ChallengeListItem,
    compute_detail_structure,
    compute_list_structure,
)

_LIST_KEY = "challenge:structure:list"
_DETAIL_PREFIX = "challenge:structure:detail:"
_TTL = timedelta(seconds=60)

_list_adapter: TypeAdapter[list[ChallengeListItem]] = TypeAdapter(
    list[ChallengeListItem]
)
_detail_adapter: TypeAdapter[ChallengeDetailStructure] = TypeAdapter(
    ChallengeDetailStructure
)


async def get_list_structure(
    session: AsyncSession,
    redis: Redis,
    ttl: timedelta = _TTL,
) -> list[ChallengeListItem]:
    """Return the cached challenge-list structure, recomputing when cold."""
    return await get_or_compute(
        redis,
        _LIST_KEY,
        _list_adapter,
        lambda: compute_list_structure(session),
        ttl,
    )


async def get_detail_structure(
    session: AsyncSession,
    redis: Redis,
    challenge_id: UUID,
    ttl: timedelta = _TTL,
) -> ChallengeDetailStructure:
    """Return the cached detail structure for one challenge, recomputing when cold."""
    return await get_or_compute(
        redis,
        f"{_DETAIL_PREFIX}{challenge_id}",
        _detail_adapter,
        lambda: compute_detail_structure(session, challenge_id),
        ttl,
    )


async def invalidate(redis: Redis) -> None:
    """Drop every cached challenge structure (the list and all details)."""
    keys: list[str] = [_LIST_KEY]
    async for key in redis.scan_iter(f"{_DETAIL_PREFIX}*"):
        keys.append(key)
    await redis.delete(*keys)
