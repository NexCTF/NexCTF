"""Emit a system event: persists it to DB and broadcasts via Redis."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model.event import Event

# Maps a full ``event_type`` to the lens an admin reviews it through. Anything
# not listed here (notably the auto-audited CRUD events) is treated as ``admin``.
EVENT_CATEGORIES: dict[str, str] = {
    "user.register": "account",
    "user.login": "account",
    "user.logout": "account",
    "user.login_failed": "security",
    "user.password_reset": "account",
    "user.totp_enabled": "account",
    "user.totp_disabled": "account",
    "user.token_created": "account",
    "user.token_revoked": "account",
    "user.oauth_unlinked": "account",
    "team.created": "gameplay",
    "team.joined": "gameplay",
    "team.left": "gameplay",
    "submission.correct": "gameplay",
    "submission.wrong": "gameplay",
    "hint.unlock": "gameplay",
    "challenge.complete": "gameplay",
    "score_adjustment.created": "admin",
    "score_adjustment.deleted": "admin",
    "admin.user_updated": "admin",
    "admin.user_totp_reset": "admin",
    "admin.user_password_reset_token": "admin",
    "admin.user_deleted": "admin",
    "admin.submission_deleted": "admin",
}

DEFAULT_CATEGORY = "admin"


def category_for(event_type: str) -> str:
    """Return the audit category for an event type, defaulting to ``admin``."""
    return EVENT_CATEGORIES.get(event_type, DEFAULT_CATEGORY)


async def emit(
    session: AsyncSession,
    redis: Redis | None = None,
    *,
    event_type: str,
    actor_id: UUID | None = None,
    target_type: str | None = None,
    target_id: UUID | None = None,
    target_label: str | None = None,
    ip: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Event:
    """Persist an Event row and publish it to the ``events:admin`` Redis channel.

    When ``redis`` is omitted the row is still persisted but no live broadcast is
    sent; this lets the CRUD layer emit audit events without a Redis handle.
    """
    event = Event(
        event_type=event_type,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        ip=ip,
        meta=meta or {},
    )
    session.add(event)
    await session.flush()

    if redis is not None:
        payload = json.dumps(
            {
                "id": str(event.id),
                "event_type": event_type,
                "actor_id": str(actor_id) if actor_id else None,
                "target_type": target_type,
                "target_id": str(target_id) if target_id else None,
                "target_label": target_label,
                "ip": ip,
                "meta": meta or {},
            }
        )
        await redis.publish("events:admin", payload)
    return event
