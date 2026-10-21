"""Server-side records of signed-in browser sessions."""

from __future__ import annotations

import heapq
import logging
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple
from uuid import UUID

from fastapi import Request
from fastapi_multiauth import hash_token
from sqlalchemy import (
    ColumnElement,
    Row,
    Uuid,
    case,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.core import appconfig
from nexctf.enums import SessionWindow
from nexctf.model import (
    Event,
    Team,
    User,
    UserSession,
    UserToken,
)
from nexctf.schema.user import (
    AdminAddressAccountRead,
    AdminFailedLoginAddressRead,
    AdminFailedLoginOverviewRead,
    AdminFailedLoginUsernameRead,
    AdminSessionOverviewRead,
    AdminSharedAddressRead,
    AdminUserIpRead,
    UserPasswordUpdate,
)
from nexctf.util.ip import get_client_ip

logger = logging.getLogger(__name__)

SESSION_TTL = 86400  # 24 h
USER_AGENT_MAX = 512
LAST_SEEN_THROTTLE = timedelta(minutes=5)
LOGIN_EVENT = "user.login"
FAILED_LOGIN_EVENT = "user.login_failed"
DAY_WINDOW = timedelta(hours=24)
FAILED_USERNAME_LIMIT = 20
FAILED_USERNAME_MAX = 64
IDLE_TIMEOUT_KEY = "auth.session_idle_minutes"
TOKEN_RETENTION = timedelta(days=7)
PURGE_BATCH = 10_000


class AccountOrigin(NamedTuple):
    """The addresses one account is reached from, and when it last signed in."""

    addresses: list[AdminUserIpRead]
    last_login_at: datetime | None


class _Grouping(NamedTuple):
    """Accounts grouped by address, with the totals they were built from."""

    addresses: dict[str, list[AdminAddressAccountRead]]
    session_count: int
    account_count: int


def session_idle(overrides: dict[str, str]) -> timedelta | None:
    """The configured idle timeout, None when it is disabled."""
    minutes = int(appconfig.get_with_overrides(IDLE_TIMEOUT_KEY, overrides))
    return timedelta(minutes=minutes) if minutes else None


def live_filter(now: datetime, idle: timedelta | None) -> list[ColumnElement[bool]]:
    """Conditions keeping sessions live at *now*: unexpired and not idle."""
    conditions = [UserSession.expires_at > now]
    if idle is not None:
        conditions.append(UserSession.last_seen_at > now - idle)
    return conditions


def team_meta(user: User) -> dict[str, str | None]:
    """The team a user acts under, recorded on the events they trigger."""
    return {"team_id": str(user.team_id) if user.team_id else None}


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


async def rotate_session(db: AsyncSession, old_sid: str, new_sid: str) -> bool:
    """Move a live session onto *new_sid*, keeping its row. False when none matched."""
    moved = await db.scalar(
        update(UserSession)
        .where(
            UserSession.sid_hash == hash_token(old_sid),
            UserSession.expires_at > datetime.now(UTC),
        )
        .values(sid_hash=hash_token(new_sid))
        .returning(UserSession.id)
    )
    return moved is not None


async def touch_live_session(
    db: AsyncSession, sid: str, user_id: UUID, idle: timedelta | None
) -> bool:
    """Return whether *sid* is live for *user_id*, refreshing its last-seen time."""
    now = datetime.now(UTC)
    row = await crud.UserSessionCrud.first(
        session=db,
        filters=[
            UserSession.sid_hash == hash_token(sid),
            UserSession.user_id == user_id,
            *live_filter(now, idle),
        ],
    )
    if row is None:
        return False
    throttle = LAST_SEEN_THROTTLE if idle is None else min(LAST_SEEN_THROTTLE, idle / 2)
    if now - row.last_seen_at >= throttle:
        row.last_seen_at = now
    return True


async def live_sessions(
    db: AsyncSession, user_id: UUID, idle: timedelta | None
) -> Sequence[UserSession]:
    """A user's live sessions, most recently active first."""
    return await crud.UserSessionCrud.get_multi(
        session=db,
        filters=[UserSession.user_id == user_id, *live_filter(datetime.now(UTC), idle)],
        order_by=UserSession.last_seen_at.desc(),
    )


async def account_origin(
    db: AsyncSession, user_id: UUID, idle: timedelta | None
) -> AccountOrigin:
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
        (row.ip, row.last_ip) for row in await live_sessions(db, user_id, idle)
    )
    if not pairs and login is not None and login.ip is not None:
        pairs = {(login.ip, login.ip): None}
    return AccountOrigin(
        addresses=[AdminUserIpRead(ip=ip, last_ip=last_ip) for ip, last_ip in pairs],
        last_login_at=login.created_at if login is not None else None,
    )


async def sessions_by_address(
    db: AsyncSession, window: SessionWindow, idle: timedelta | None
) -> AdminSessionOverviewRead:
    """Accounts grouped by the addresses they are reached from over *window*."""
    if window is SessionWindow.LIVE:
        grouping = await _live_grouping(db, idle)
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


async def _live_grouping(db: AsyncSession, idle: timedelta | None) -> _Grouping:
    """Live sessions, grouped by every address they are reached from."""
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
            .where(*live_filter(datetime.now(UTC), idle))
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
    # Logins recorded before the event carried a team fall back to the current one
    login_team_id = case(
        (Event.meta.has_key("team_id"), Event.meta["team_id"].astext.cast(Uuid)),
        else_=User.team_id,
    )
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
        .outerjoin(Team, Team.id == login_team_id)
        .where(Event.event_type == LOGIN_EVENT, Event.ip.is_not(None))
        .group_by(Event.ip, Event.actor_id, User.username, Team.id, Team.name)
    )
    rows = (await db.execute(stmt.where(*window_filters(window)))).all()

    addresses: dict[str, list[AdminAddressAccountRead]] = defaultdict(list)
    for (ip, user_id), team_rows in _by_address_account(rows).items():
        latest = max(team_rows, key=lambda row: row.last_seen_at)
        addresses[ip].append(
            AdminAddressAccountRead(
                user_id=user_id,
                username=latest.username,
                team_id=latest.team_id,
                team_name=latest.team_name,
                session_count=sum(row.logins for row in team_rows),
                last_seen_at=latest.last_seen_at,
                user_agent=None,
                opened_here=True,
            )
        )

    return _Grouping(
        addresses=addresses,
        session_count=sum(row.logins for row in rows),
        account_count=len({row.actor_id for row in rows}),
    )


def _by_address_account(rows: Sequence[Row]) -> dict[tuple[str, UUID], list[Row]]:
    """Login rows per (address, account), one row per team signed in under."""
    grouped: dict[tuple[str, UUID], list[Row]] = defaultdict(list)
    for row in rows:
        grouped[(row.ip, row.actor_id)].append(row)
    return grouped


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
    rows = (await db.execute(stmt.where(*window_filters(window)))).all()

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


def window_filters(window: SessionWindow, column: Any = Event.created_at) -> list[Any]:
    """Conditions keeping rows whose *column* falls in *window*; ``live`` is 24 hours."""
    if window is SessionWindow.ALL:
        return []
    return [column >= datetime.now(UTC) - DAY_WINDOW]


async def track_session_ip(db: AsyncSession, sid: str, ip: str | None) -> None:
    """Record the IP *sid* is currently used from, writing only when it changed."""
    row = await crud.UserSessionCrud.first(
        session=db, filters=[UserSession.sid_hash == hash_token(sid)]
    )
    if row is not None and row.last_ip != ip:
        logger.info(
            "session moved from %s to %s",
            row.last_ip,
            ip,
            extra={"previous_ip": row.last_ip, "session_id": str(row.id)},
        )
        row.last_ip = ip


async def revoke_session(db: AsyncSession, sid: str) -> None:
    """Revoke a single session by its cookie session id."""
    logger.info("session revoked")
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
    logger.info("session revoked", extra={"session_id": str(row.id)})
    await crud.UserSessionCrud.delete(session=db, filters=[UserSession.id == row.id])
    return True


async def revoke_user_sessions(db: AsyncSession, user: User) -> None:
    """Revoke every session for a user, on every device."""
    logger.info("all sessions revoked for %s", user.username)
    await crud.UserSessionCrud.delete(
        session=db, filters=[UserSession.user_id == user.id]
    )


async def purge_expired_access(db: AsyncSession) -> None:
    """Delete expired sessions, and API tokens expired over ``TOKEN_RETENTION``."""
    now = datetime.now(UTC)
    while await _purge_session_batch(db, now) == PURGE_BATCH:
        pass
    await db.execute(
        delete(UserToken).where(UserToken.expires_at < now - TOKEN_RETENTION)
    )


async def _purge_session_batch(db: AsyncSession, now: datetime) -> int:
    """Delete and commit up to ``PURGE_BATCH`` expired sessions, returning how many."""
    expired = select(UserSession.id).where(UserSession.expires_at < now)
    deleted = await db.scalars(
        delete(UserSession)
        .where(UserSession.id.in_(expired.limit(PURGE_BATCH)))
        .returning(UserSession.id)
    )
    count = len(deleted.all())
    await db.commit()
    return count


async def revoke_all_access(db: AsyncSession, user: User) -> None:
    """Revoke every session and API token a user holds."""
    await revoke_user_sessions(db, user)
    await crud.UserTokenCrud.delete(db, filters=[UserToken.user_id == user.id])


async def replace_password(db: AsyncSession, user: User, hashed_password: str) -> None:
    """Store a new password hash, voiding reset tokens, sessions and API tokens."""
    session_version = user.session_version + 1
    await crud.UserCrud.update(
        session=db,
        filters=[User.id == user.id],
        obj=UserPasswordUpdate(
            id=user.id,
            hashed_password=hashed_password,
            session_version=session_version,
        ),
    )
    # Reflect the bump on the instance so a re-issued cookie carries it.
    user.session_version = session_version
    await revoke_all_access(db, user)
