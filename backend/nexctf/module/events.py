"""Emit a system event: persists it to DB and broadcasts via Redis."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model.event import Event


async def emit(
    session: AsyncSession,
    redis: Redis,
    *,
    event_type: str,
    actor_id: UUID | None = None,
    team_id: UUID | None = None,
    challenge_id: UUID | None = None,
    ip: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Event:
    """Persist an Event row and publish it to the ``events:admin`` Redis channel."""
    event = Event(
        event_type=event_type,
        actor_id=actor_id,
        team_id=team_id,
        challenge_id=challenge_id,
        ip=ip,
        meta=meta or {},
    )
    session.add(event)
    await session.flush()

    payload = json.dumps(
        {
            "id": str(event.id),
            "event_type": event_type,
            "actor_id": str(actor_id) if actor_id else None,
            "team_id": str(team_id) if team_id else None,
            "challenge_id": str(challenge_id) if challenge_id else None,
            "ip": ip,
            "meta": meta or {},
        }
    )
    await redis.publish("events:admin", payload)
    return event
