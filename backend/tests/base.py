"""Shared helpers and permission-guard mixins for API test classes.

Each mixin requires the subclass to define a ``PREFIX: str`` class variable.
Auth is checked before request-body validation, so minimal/empty payloads
are sufficient to trigger a 403 without needing a valid body.
"""

import time
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from fastapi_multiauth import hash_token
from httpx import AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.enums import ClientSource
from nexctf.model import Event, Team, User, UserAgentSighting, UserSession, UserToken
from nexctf.model.question import Question
from nexctf.module.session import LOGIN_EVENT
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

NULL_UUID = "00000000-0000-0000-0000-000000000000"
FUTURE = "2099-01-01T00:00:00+00:00"
PAST = "2000-01-01T00:00:00+00:00"


@contextmanager
def signed_ago(seconds: int) -> Generator[None]:
    """Sign every cookie minted inside the block *seconds* in the past."""
    with patch.object(
        TimestampSigner, "get_timestamp", lambda _: int(time.time()) - seconds
    ):
        yield


@asynccontextmanager
async def second_device(
    client_factory, username: str, password: str
) -> AsyncGenerator[AsyncClient]:
    """Log the same user in from a second client, as another browser would."""
    async with client_factory() as c:
        resp = await c.post(
            "/auth/token", data={"username": username, "password": password}
        )
        assert resp.status_code == 204
        yield c


async def add_session(
    db_session: AsyncSession,
    user: User,
    *,
    ip: str | None,
    last_ip: str | None = None,
    minutes_ago: int = 0,
    expires_in: timedelta = timedelta(hours=1),
) -> UserSession:
    """Give *user* a session last used *minutes_ago*, expiring in *expires_in*."""
    now = datetime.now(UTC)
    row = UserSession(
        user_id=user.id,
        sid_hash=uuid4().hex,
        ip=ip,
        last_ip=last_ip if last_ip is not None else ip,
        user_agent="Mozilla/5.0",
        last_seen_at=now - timedelta(minutes=minutes_ago),
        expires_at=now + expires_in,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def add_sighting(
    db_session: AsyncSession,
    user: User,
    user_agent: str,
    *,
    source: ClientSource = ClientSource.cookie,
    token: UserToken | None = None,
    hours_ago: float = 0,
) -> UserAgentSighting:
    """Record that *user* was seen with *user_agent*, through *token* if given."""
    seen = datetime.now(UTC) - timedelta(hours=hours_ago)
    row = UserAgentSighting(
        user_id=user.id,
        team_id=user.team_id,
        token_id=token.id if token else None,
        token_name=token.name if token else None,
        user_agent=user_agent,
        ua_hash=hash_token(user_agent),
        source=ClientSource.token if token else source,
        first_seen_at=seen,
        last_seen_at=seen,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def add_login(
    db_session: AsyncSession,
    user: User,
    *,
    ip: str | None,
    hours_ago: float = 0,
    team_meta: dict[str, str | None] | None = None,
) -> Event:
    """Record a sign-in by *user* from *ip*, *hours_ago*."""
    row = Event(
        event_type=LOGIN_EVENT,
        actor_id=user.id,
        ip=ip,
        meta={"username": user.username, **(team_meta or {})},
        created_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def session_row(db_session: AsyncSession, user: User) -> UserSession:
    """*user*'s only session, reloaded from the database."""
    return (
        await db_session.execute(
            select(UserSession)
            .where(UserSession.user_id == user.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def put_in_team(db_session: AsyncSession, user: User) -> Team:
    """Create a team and move *user* into it."""
    team = Team(name="MyTeam", invite_code="MYTEAM01")
    db_session.add(team)
    await db_session.flush()
    user.team_id = team.id
    await db_session.flush()
    return team


async def make_user(
    db_session: AsyncSession, username: str, team: Team | None = None
) -> User:
    """Create a user, optionally on *team*."""
    user = User(username=username, team_id=team.id if team else None)
    db_session.add(user)
    await db_session.flush()
    return user


async def make_team(db_session: AsyncSession, name: str) -> Team:
    """Create a team with an invite code derived from *name*."""
    team = Team(name=name, invite_code=name.upper()[:8].ljust(8, "0"))
    db_session.add(team)
    await db_session.flush()
    return team


async def make_solvable(
    db_session: AsyncSession, user: User, flag: str
) -> tuple[StandardChallenge, Question]:
    """Put *user* in a team and create an active challenge the flag solves."""
    await put_in_team(db_session, user)
    challenge = StandardChallenge(title="Hook Test", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    question = Question(label="Q", points=100, challenge_id=challenge.id)
    db_session.add(question)
    await db_session.flush()
    db_session.add(MatchSolution(value=flag, question_id=question.id))
    return challenge, question


async def get_data(client: AsyncClient, url: str) -> Any:
    """GET *url*, expect a 200, and return its ``data`` payload."""
    resp = await client.get(url)
    assert resp.status_code == 200
    return resp.json()["data"]


async def define_custom_field(
    client: AsyncClient, name: str, target: str, **extra: Any
) -> str:
    """Create a custom field definition through the admin API, returning its id."""
    resp = await client.post(
        "/admin/custom-field",
        json={"name": name, "label": name.title(), "target": target, **extra},
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


async def custom_field_values(client: AsyncClient, url: str) -> dict[str, str | None]:
    """GET a team/user detail *url*, returning its values keyed by definition id."""
    data = await get_data(client, url)
    return {v["definition"]["id"]: v["value"] for v in data["custom_field_values"]}


class ListGuardMixin:
    PREFIX: str

    async def test_requires_auth(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX)
        assert resp.status_code in (307, 401)

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 403


class CreateGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.post(self.PREFIX, json={})
        assert resp.status_code == 403


class GetItemGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 403


class UpdateGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.put(f"{self.PREFIX}/{NULL_UUID}", json={"id": NULL_UUID})
        assert resp.status_code == 403


class DeleteGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 403
