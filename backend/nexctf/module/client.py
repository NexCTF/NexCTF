"""User-agents each account is seen with, and the kind of client behind them."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
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
SIGNATURE_AGENT_MAX = 255
SIGNATURE_AGENT_URL = re.compile(r'"(https://[^"]+)"')
UA_PLATFORMS = (
    ("Windows", "Windows"),
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Macintosh", "macOS"),
    ("Android", "Android"),
    ("CrOS", "Chrome OS"),
    ("Linux", "Linux"),
)
# (user-agent platform, Sec-CH-UA-Platform) pairs real browsers send
COMPATIBLE_PLATFORMS = {("Linux", "Android"), ("Linux", "Chrome OS")}


def signature_agent_host(header: str | None) -> str | None:
    """Host named by a Signature-Agent header, or the raw value if it names none."""
    header = (header or "").strip()
    if not header:
        return None
    host = None
    if match := SIGNATURE_AGENT_URL.search(header):
        try:
            host = urlsplit(match.group(1)).hostname
        except ValueError:
            pass
    return (host or header)[:SIGNATURE_AGENT_MAX]


def platforms_disagree(user_agent: str, platform_hint: str | None) -> bool:
    """Whether Sec-CH-UA-Platform names another OS than the user-agent."""
    hinted = (platform_hint or "").strip().strip('"')
    if hinted in ("", "Unknown"):
        return False
    claimed = next((name for token, name in UA_PLATFORMS if token in user_agent), None)
    return (
        claimed not in (None, hinted) and (claimed, hinted) not in COMPATIBLE_PLATFORMS
    )


@dataclass(frozen=True)
class ClientInfo:
    """The client behind an authenticated request."""

    user_agent: str
    token_id: UUID | None = None
    token_name: str | None = None
    signature_agent: str | None = None
    platform_mismatch: bool = False

    @classmethod
    def from_headers(
        cls,
        headers: Mapping[str, str],
        token_id: UUID | None,
        token_name: str | None = None,
    ) -> ClientInfo:
        """Describe a client from its request headers and authenticating token."""
        user_agent = (headers.get("user-agent") or "")[:USER_AGENT_MAX]
        return cls(
            user_agent=user_agent,
            token_id=token_id,
            token_name=token_name,
            signature_agent=signature_agent_host(headers.get("signature-agent")),
            platform_mismatch=platforms_disagree(
                user_agent, headers.get("sec-ch-ua-platform")
            ),
        )

    @property
    def signals(self) -> tuple[str | None, bool]:
        """Agent signals sent besides the user-agent."""
        return self.signature_agent, self.platform_mismatch

    @property
    def source(self) -> ClientSource:
        """How the client authenticated."""
        return ClientSource.cookie if self.token_id is None else ClientSource.token

    def event_meta(self) -> dict[str, str | bool]:
        """The fields recorded on the events this client triggers."""
        meta: dict[str, str | bool] = {
            "user_agent": self.user_agent,
            "source": self.source.value,
        }
        if self.signature_agent:
            meta["signature_agent"] = self.signature_agent
        if self.platform_mismatch:
            meta["platform_mismatch"] = True
        return meta


def _seen_key(user: User, client: ClientInfo, digest: str) -> str:
    """Throttle key for one user, source, user-agent and set of agent signals."""
    key = f"{SEEN_KEY_PREFIX}{user.id}:{client.source.value}:{digest}"
    if any(client.signals):
        key += f":{hash_token(repr(client.signals))}"
    return key


async def record_sighting(redis: Redis, user: User, client: ClientInfo) -> None:
    """Record that *user* is using *client*, at most once per throttle window."""
    digest = hash_token(client.user_agent)
    key = _seen_key(user, client, digest)
    if not await redis.set(key, "1", nx=True, ex=SIGHTING_THROTTLE):
        return
    now = datetime.now(UTC)
    stmt = insert(UserAgentSighting).values(
        user_id=user.id,
        team_id=user.team_id,
        token_id=client.token_id,
        token_name=client.token_name,
        user_agent=client.user_agent,
        ua_hash=digest,
        source=client.source,
        signature_agent=client.signature_agent,
        platform_mismatch=client.platform_mismatch,
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
            "token_name": stmt.excluded.token_name,
            "signature_agent": func.coalesce(
                stmt.excluded.signature_agent, UserAgentSighting.signature_agent
            ),
            "platform_mismatch": or_(
                UserAgentSighting.platform_mismatch, stmt.excluded.platform_mismatch
            ),
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
        (
            or_(
                UserAgentSighting.signature_agent.is_not(None),
                _matches_any(user_agent, ai),
            ),
            ClientCategory.AI.value,
        ),
        (
            or_(user_agent == "", _matches_any(user_agent, automation)),
            ClientCategory.AUTOMATION.value,
        ),
        else_=ClientCategory.BROWSER.value,
    )


def sighting_load_options(category: ColumnElement[str]) -> list[ExecutableOption]:
    """Load a sighting's relations along with its *category*."""
    return [
        *(crud.UserAgentSightingCrud.default_load_options or ()),
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
