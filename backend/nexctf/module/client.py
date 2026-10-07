"""User-agents each account is seen with, and the kind of client behind them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi_multiauth import hash_token
from redis.asyncio import Redis
from sqlalchemy import ColumnElement, case, distinct, false, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_expression
from sqlalchemy.sql.base import ExecutableOption

from nexctf import crud
from nexctf.core import appconfig
from nexctf.core.db import get_auth_db_context
from nexctf.enums import ClientCategory, ClientSource, SessionWindow
from nexctf.model import User, UserAgentSighting
from nexctf.module.session import USER_AGENT_MAX, window_filters
from nexctf.schema.user import AdminClientSummaryRead, AdminUserClientRead

AI_PATTERNS_KEY = "clients.ai_patterns"
AUTOMATION_PATTERNS_KEY = "clients.automation_patterns"
SIGHTING_THROTTLE = timedelta(minutes=5)
SEEN_KEY_PREFIX = "client_seen:"


@dataclass(frozen=True)
class ClientInfo:
    """The client behind an authenticated request."""

    user_agent: str
    token_id: UUID | None = None

    @classmethod
    def build(cls, user_agent: str | None, token_id: UUID | None) -> ClientInfo:
        """Describe a client from its raw header and authenticating token."""
        return cls(user_agent=(user_agent or "")[:USER_AGENT_MAX], token_id=token_id)

    @property
    def source(self) -> ClientSource:
        """How the client authenticated."""
        return ClientSource.cookie if self.token_id is None else ClientSource.token

    def event_meta(self) -> dict[str, str]:
        """The fields recorded on the events this client triggers."""
        return {"user_agent": self.user_agent, "source": self.source.value}


async def record_sighting(redis: Redis, user: User, client: ClientInfo) -> None:
    """Record that *user* is using *client*, at most once per throttle window."""
    digest = hash_token(client.user_agent)
    key = f"{SEEN_KEY_PREFIX}{user.id}:{client.source.value}:{digest}"
    if not await redis.set(key, "1", nx=True, ex=SIGHTING_THROTTLE):
        return
    now = datetime.now(UTC)
    stmt = insert(UserAgentSighting).values(
        user_id=user.id,
        team_id=user.team_id,
        token_id=client.token_id,
        user_agent=client.user_agent,
        ua_hash=digest,
        source=client.source,
        first_seen_at=now,
        last_seen_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_agent_sighting",
        set_={
            "last_seen_at": now,
            "updated_at": now,
            "team_id": stmt.excluded.team_id,
            "token_id": stmt.excluded.token_id,
        },
    )
    async with get_auth_db_context() as db:
        await db.execute(stmt)


def _patterns(key: str, overrides: dict[str, str]) -> list[str]:
    raw = str(appconfig.get_with_overrides(key, overrides))
    return [line.strip().lower() for line in raw.splitlines() if line.strip()]


def _matches_any(user_agent: Any, patterns: list[str]) -> ColumnElement:
    lowered = func.lower(user_agent)
    return or_(
        false(), *(lowered.contains(pattern, autoescape=True) for pattern in patterns)
    )


def category_expression(overrides: dict[str, str]) -> ColumnElement[str]:
    """Classify a sighting's user-agent in SQL from the configured patterns."""
    user_agent = UserAgentSighting.user_agent
    ai = _patterns(AI_PATTERNS_KEY, overrides)
    automation = _patterns(AUTOMATION_PATTERNS_KEY, overrides)
    return case(
        (_matches_any(user_agent, ai), ClientCategory.AI.value),
        (
            or_(user_agent == "", _matches_any(user_agent, automation)),
            ClientCategory.AUTOMATION.value,
        ),
        else_=ClientCategory.BROWSER.value,
    )


def sighting_load_options(category: ColumnElement[str]) -> list[ExecutableOption]:
    """Load a sighting's relations along with its *category*."""
    return [
        *crud.UserAgentSightingCrud.default_load_options,
        with_expression(UserAgentSighting.category, category),
    ]


async def user_clients(
    db: AsyncSession, user_id: UUID, category: ColumnElement[str]
) -> list[AdminUserClientRead]:
    """Every client one account was seen with, most recently active first."""
    rows = await crud.UserAgentSightingCrud.get_multi(
        db,
        filters=[UserAgentSighting.user_id == user_id],
        load_options=sighting_load_options(category),
        order_by=UserAgentSighting.last_seen_at.desc(),
    )
    return [AdminUserClientRead.model_validate(row) for row in rows]


async def clients_summary(
    db: AsyncSession, window: SessionWindow, category: ColumnElement[str]
) -> AdminClientSummaryRead:
    """How many clients and accounts were seen over *window*, per kind."""
    user_id = UserAgentSighting.user_id

    def accounts_where(condition: ColumnElement[bool]) -> ColumnElement[int]:
        return func.count(distinct(user_id)).filter(condition)

    row = (
        await db.execute(
            select(
                func.count(distinct(UserAgentSighting.ua_hash)).label("client_count"),
                func.count(distinct(user_id)).label("account_count"),
                accounts_where(category == ClientCategory.AI.value).label(
                    "ai_account_count"
                ),
                accounts_where(category == ClientCategory.AUTOMATION.value).label(
                    "automation_account_count"
                ),
                accounts_where(UserAgentSighting.source == ClientSource.token).label(
                    "token_account_count"
                ),
            ).where(*window_filters(window, UserAgentSighting.last_seen_at))
        )
    ).one()
    return AdminClientSummaryRead.model_validate(row._mapping)
