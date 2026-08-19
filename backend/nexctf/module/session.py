"""Server-side records of signed-in browser sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Request
from fastapi_multiauth import hash_token
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.model import User, UserSession
from nexctf.util.ip import get_client_ip

SESSION_TTL = 86400  # 24 h
USER_AGENT_MAX = 512
LAST_SEEN_THROTTLE = timedelta(minutes=5)


async def start_session(
    db: AsyncSession, sid: str, *, user: User, request: Request
) -> None:
    """Record a freshly minted cookie session id as live."""
    now = datetime.now(UTC)
    ua = request.headers.get("user-agent")
    db.add(
        UserSession(
            user_id=user.id,
            sid_hash=hash_token(sid),
            ip=get_client_ip(request),
            user_agent=ua[:USER_AGENT_MAX] if ua else None,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=SESSION_TTL),
        )
    )
    await db.flush()


async def touch_live_session(db: AsyncSession, sid: str, user_id: UUID) -> bool:
    """Return whether *sid* is live for *user_id*, refreshing its last-seen time."""
    now = datetime.now(UTC)
    row = await crud.UserSessionCrud.first(
        session=db,
        filters=[
            UserSession.sid_hash == hash_token(sid),
            UserSession.user_id == user_id,
            UserSession.expires_at > now,
        ],
    )
    if row is None:
        return False
    if now - row.last_seen_at >= LAST_SEEN_THROTTLE:
        row.last_seen_at = now
    return True


async def revoke_session(db: AsyncSession, sid: str) -> None:
    """Revoke a single session by its cookie session id."""
    await crud.UserSessionCrud.delete(
        session=db, filters=[UserSession.sid_hash == hash_token(sid)]
    )


async def revoke_user_sessions(db: AsyncSession, user: User) -> None:
    """Revoke every session for a user, on every device."""
    await crud.UserSessionCrud.delete(
        session=db, filters=[UserSession.user_id == user.id]
    )
