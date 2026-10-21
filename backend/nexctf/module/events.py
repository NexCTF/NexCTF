"""Emit a system event: persists it to DB and broadcasts via Redis."""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.eventbus import publish_event
from nexctf.model.event import Event


@dataclass(frozen=True)
class AuditContext:
    """The actor, origin and entry point of the action being served."""

    actor_id: UUID | None
    ip: str | None
    source: str | None = None


_audit_ctx: ContextVar[AuditContext | None] = ContextVar("audit_ctx", default=None)


def set_audit_context(ctx: AuditContext) -> None:
    """Bind the audit context for the current request or CLI command."""
    _audit_ctx.set(ctx)


def current_audit_context() -> AuditContext | None:
    """Return the audit context bound to the current request, if any."""
    return _audit_ctx.get()


# Maps a full ``event_type`` to the lens an admin reviews it through. Anything
# not listed here (notably the auto-audited CRUD events) is treated as ``admin``.
EVENT_CATEGORIES: frozendict[str, str] = frozendict(
    {
        "user.register": "account",
        "user.login": "account",
        "user.logout": "account",
        "user.login_failed": "security",
        "user.reauth": "account",
        "user.password_reset": "account",
        "user.password_changed": "account",
        "user.password_reset_requested": "security",
        "user.email_verified": "account",
        "user.verification_resent": "account",
        "admin.email_test": "admin",
        "user.totp_enabled": "account",
        "user.totp_disabled": "account",
        "user.token_created": "account",
        "user.token_revoked": "account",
        "user.session_revoked": "account",
        "user.sessions_revoked": "account",
        "user.oauth_unlinked": "account",
        "team.created": "gameplay",
        "team.joined": "gameplay",
        "team.left": "gameplay",
        "submission.correct": "gameplay",
        "submission.wrong": "gameplay",
        "submission.trap": "security",
        "submission.canary": "security",
        "solution.timeout": "security",
        "hint.unlock": "gameplay",
        "challenge.viewed": "gameplay",
        "challenge.complete": "gameplay",
        "challenge.feedback": "gameplay",
        "score_adjustment.created": "admin",
        "score_adjustment.deleted": "admin",
        "admin.user_updated": "admin",
        "admin.user_totp_reset": "admin",
        "admin.user_session_revoked": "admin",
        "admin.user_password_reset_token": "admin",
        "admin.user_deleted": "admin",
        "admin.submission_deleted": "admin",
    }
)

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
    A ``source`` bound in the audit context is added to *meta*.
    """
    ctx = _audit_ctx.get()
    if ctx is not None and ctx.source is not None:
        meta = {**(meta or {}), "source": ctx.source}
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
        await publish_event(redis, ["events:admin"], payload)
    return event
