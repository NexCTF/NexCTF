"""Server-side records of signed-in browser sessions."""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple
from uuid import UUID

from fastapi import Request
from fastapi_multiauth import hash_token
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.enums import SessionWindow
from nexctf.model import Event, Team, User, UserSession
from nexctf.schema.user import (
    AdminAddressAccountRead,
    AdminFailedLoginAddressRead,
    AdminFailedLoginOverviewRead,
    AdminFailedLoginUsernameRead,
    AdminSessionOverviewRead,
    AdminSharedAddressRead,
    AdminUserIpRead,
)
from nexctf.util.ip import get_client_ip

SESSION_TTL = 86400  # 24 h
USER_AGENT_MAX = 512
LAST_SEEN_THROTTLE = timedelta(minutes=5)
LOGIN_EVENT = "user.login"
FAILED_LOGIN_EVENT = "user.login_failed"
DAY_WINDOW = timedelta(hours=24)
FAILED_USERNAME_LIMIT = 20
FAILED_USERNAME_MAX = 64


class AccountOrigin(NamedTuple):
    """The addresses one account is reached from, and when it last signed in."""

    addresses: list[AdminUserIpRead]
    last_login_at: datetime | None


class _Grouping(NamedTuple):
    """Accounts grouped by address, with the totals they were built from."""

    addresses: dict[str, list[AdminAddressAccountRead]]
    session_count: int
    account_count: int


async def start_session(
    db: AsyncSession, sid: str, *, user: User, request: Request
) -> None:
    """Record a freshly minted cookie session id as live."""
    now = datetime.now(UTC)
    ua = request.headers.get("user-agent")
    ip = get_client_ip(request)
    db.add(
        UserSession(
            user_id=user.id,
            sid_hash=hash_token(sid),
            ip=ip,
            last_ip=ip,
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


async def live_sessions(db: AsyncSession, user_id: UUID) -> Sequence[UserSession]:
    """A user's unexpired sessions, most recently active first."""
    return await crud.UserSessionCrud.get_multi(
        session=db,
        filters=[
            UserSession.user_id == user_id,
            UserSession.expires_at > datetime.now(UTC),
        ],
        order_by=UserSession.last_seen_at.desc(),
    )


async def account_origin(db: AsyncSession, user_id: UUID) -> AccountOrigin:
    """One account's addresses: its live sessions, else where it last signed in."""
    login = (
        await db.execute(
            select(Event.ip, Event.created_at)
            .where(Event.actor_id == user_id, Event.event_type == LOGIN_EVENT)
            .order_by(Event.created_at.desc())
            .limit(1)
        )
    ).first()
    pairs = dict.fromkeys(
        (row.ip, row.last_ip) for row in await live_sessions(db, user_id)
    )
    if not pairs and login is not None and login.ip is not None:
        pairs = {(login.ip, login.ip): None}
    return AccountOrigin(
        addresses=[AdminUserIpRead(ip=ip, last_ip=last_ip) for ip, last_ip in pairs],
        last_login_at=login.created_at if login is not None else None,
    )


async def sessions_by_address(
    db: AsyncSession, window: SessionWindow
) -> AdminSessionOverviewRead:
    """Accounts grouped by the addresses they are reached from over *window*."""
    if window is SessionWindow.LIVE:
        grouping = await _live_grouping(db)
    else:
        grouping = await _login_grouping(db, window)

    reads = [
        _address_read(address, accounts)
        for address, accounts in grouping.addresses.items()
    ]
    return AdminSessionOverviewRead(
        session_count=grouping.session_count,
        account_count=grouping.account_count,
        address_count=len(reads),
        shared_address_count=sum(1 for a in reads if a.account_count > 1),
        cross_team_address_count=sum(1 for a in reads if a.team_count > 1),
        addresses=sorted(
            reads, key=lambda a: (a.account_count, a.last_seen_at), reverse=True
        ),
    )


async def _live_grouping(db: AsyncSession) -> _Grouping:
    """Unexpired sessions, grouped by every address they are reached from."""
    rows = (
        await db.execute(
            select(
                UserSession.ip,
                UserSession.last_ip,
                UserSession.user_agent,
                UserSession.last_seen_at,
                User.id.label("user_id"),
                User.username,
                Team.id.label("team_id"),
                Team.name.label("team_name"),
            )
            .join(User, UserSession.user_id == User.id)
            .outerjoin(Team, User.team_id == Team.id)
            .where(UserSession.expires_at > datetime.now(UTC))
        )
    ).all()

    grouped: dict[str, dict[UUID, list[Any]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        for address in {row.ip, row.last_ip} - {None}:
            grouped[address][row.user_id].append(row)

    return _Grouping(
        addresses={
            address: [
                _account_read(address, user_id, sessions)
                for user_id, sessions in accounts.items()
            ]
            for address, accounts in grouped.items()
        },
        session_count=len(rows),
        account_count=len({row.user_id for row in rows}),
    )


async def _login_grouping(db: AsyncSession, window: SessionWindow) -> _Grouping:
    """Login events, grouped by the address each account signed in from."""
    stmt = (
        select(
            Event.ip,
            Event.actor_id,
            User.username,
            Team.id.label("team_id"),
            Team.name.label("team_name"),
            func.count().label("logins"),
            func.max(Event.created_at).label("last_seen_at"),
        )
        .join(User, Event.actor_id == User.id)
        .outerjoin(Team, User.team_id == Team.id)
        .where(Event.event_type == LOGIN_EVENT, Event.ip.is_not(None))
        .group_by(Event.ip, Event.actor_id, User.username, Team.id, Team.name)
    )
    rows = (await db.execute(_since(stmt, window))).all()

    addresses: dict[str, list[AdminAddressAccountRead]] = defaultdict(list)
    for row in rows:
        addresses[row.ip].append(
            AdminAddressAccountRead(
                user_id=row.actor_id,
                username=row.username,
                team_id=row.team_id,
                team_name=row.team_name,
                session_count=row.logins,
                last_seen_at=row.last_seen_at,
                user_agent=None,
                opened_here=True,
            )
        )

    return _Grouping(
        addresses=addresses,
        session_count=sum(row.logins for row in rows),
        account_count=len({row.actor_id for row in rows}),
    )


def _account_read(
    address: str, user_id: UUID, sessions: list[Any]
) -> AdminAddressAccountRead:
    """One account's footprint on a single address."""
    latest = max(sessions, key=lambda row: row.last_seen_at)
    return AdminAddressAccountRead(
        user_id=user_id,
        username=latest.username,
        team_id=latest.team_id,
        team_name=latest.team_name,
        session_count=len(sessions),
        last_seen_at=latest.last_seen_at,
        user_agent=latest.user_agent,
        opened_here=any(row.ip == address for row in sessions),
    )


def _address_read(
    address: str, accounts: list[AdminAddressAccountRead]
) -> AdminSharedAddressRead:
    """Build the read model for one address from the accounts grouped under it."""
    reads = sorted(accounts, key=lambda a: a.last_seen_at, reverse=True)
    teams = {a.team_id for a in reads}
    return AdminSharedAddressRead(
        ip=address,
        account_count=len(reads),
        session_count=sum(a.session_count for a in reads),
        same_team=len(reads) > 1 and len(teams) == 1 and None not in teams,
        team_count=len(teams - {None}),
        last_seen_at=reads[0].last_seen_at,
        accounts=reads,
    )


async def failed_logins_by_address(
    db: AsyncSession, window: SessionWindow
) -> AdminFailedLoginOverviewRead:
    """Failed logins grouped by the address they came from, over *window*."""
    username = func.left(Event.meta["username"].astext, FAILED_USERNAME_MAX)
    stmt = (
        select(
            Event.ip,
            username.label("username"),
            Event.actor_id,
            func.count().label("attempts"),
            func.max(Event.created_at).label("last_attempt_at"),
        )
        .where(
            Event.event_type == FAILED_LOGIN_EVENT,
            Event.ip.is_not(None),
            username.is_not(None),
        )
        .group_by(Event.ip, username, Event.actor_id)
    )
    rows = (await db.execute(_since(stmt, window))).all()

    addresses: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        addresses[row.ip].append(row)

    reads = [_failed_login_read(ip, tried) for ip, tried in addresses.items()]
    return AdminFailedLoginOverviewRead(
        attempt_count=sum(row.attempts for row in rows),
        address_count=len(reads),
        spray_address_count=sum(1 for a in reads if a.username_count > 1),
        addresses=sorted(
            reads,
            key=lambda a: (a.username_count, a.attempt_count, a.last_attempt_at),
            reverse=True,
        ),
    )


def _failed_login_read(address: str, tried: list[Any]) -> AdminFailedLoginAddressRead:
    """Build the read model for one address, listing its top usernames only."""
    top = heapq.nlargest(
        FAILED_USERNAME_LIMIT,
        tried,
        key=lambda row: (row.actor_id is not None, row.attempts, row.last_attempt_at),
    )
    return AdminFailedLoginAddressRead(
        ip=address,
        attempt_count=sum(row.attempts for row in tried),
        username_count=len({row.username for row in tried}),
        known_username_count=len(
            {row.username for row in tried if row.actor_id is not None}
        ),
        last_attempt_at=max(row.last_attempt_at for row in tried),
        usernames=[
            AdminFailedLoginUsernameRead(
                username=row.username,
                user_id=row.actor_id,
                attempt_count=row.attempts,
                last_attempt_at=row.last_attempt_at,
            )
            for row in top
        ],
    )


def _since(stmt: Select[Any], window: SessionWindow) -> Select[Any]:
    """Limit an events query to *window*; ``live`` covers the last 24 hours."""
    if window is SessionWindow.ALL:
        return stmt
    return stmt.where(Event.created_at >= datetime.now(UTC) - DAY_WINDOW)


async def track_session_ip(db: AsyncSession, sid: str, ip: str | None) -> None:
    """Record the IP *sid* is currently used from, writing only when it changed."""
    row = await crud.UserSessionCrud.first(
        session=db, filters=[UserSession.sid_hash == hash_token(sid)]
    )
    if row is not None and row.last_ip != ip:
        row.last_ip = ip


async def revoke_session(db: AsyncSession, sid: str) -> None:
    """Revoke a single session by its cookie session id."""
    await crud.UserSessionCrud.delete(
        session=db, filters=[UserSession.sid_hash == hash_token(sid)]
    )


async def revoke_session_by_id(
    db: AsyncSession, session_id: UUID, user_id: UUID
) -> bool:
    """Revoke one session, but only if *user_id* owns it. False when it does not."""
    row = await crud.UserSessionCrud.first(
        session=db,
        filters=[UserSession.id == session_id, UserSession.user_id == user_id],
    )
    if row is None:
        return False
    await crud.UserSessionCrud.delete(session=db, filters=[UserSession.id == row.id])
    return True


async def revoke_user_sessions(db: AsyncSession, user: User) -> None:
    """Revoke every session for a user, on every device."""
    await crud.UserSessionCrud.delete(
        session=db, filters=[UserSession.user_id == user.id]
    )
