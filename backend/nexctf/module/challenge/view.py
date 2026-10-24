"""The first time each user opens a challenge."""

from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import User
from nexctf.module.client import ClientInfo
from nexctf.module.events import emit
from nexctf.module.session import team_meta

VIEWED_KEY_PREFIX = "challenge_viewed:"


async def record_first_view(
    session: AsyncSession,
    redis: Redis,
    user: User,
    challenge_id: UUID,
    title: str,
    ip: str | None,
    client: ClientInfo,
) -> None:
    """Emit ``challenge.viewed`` the first time a user opens a challenge."""
    if not await redis.set(
        f"{VIEWED_KEY_PREFIX}{user.id}:{challenge_id}", "1", nx=True
    ):
        return
    await emit(
        session,
        event_type="challenge.viewed",
        actor_id=user.id,
        target_type="challenges",
        target_id=challenge_id,
        target_label=title,
        ip=ip,
        meta={**team_meta(user), **client.event_meta()},
    )
