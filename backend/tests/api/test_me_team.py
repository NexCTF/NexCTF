"""Tests for the team membership endpoints and the team-changes lock."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core import appconfig
from nexctf.model import Team, User


async def _put_in_team(db_session: AsyncSession, user: User) -> Team:
    team = Team(name="MyTeam", invite_code="MYTEAM01")
    db_session.add(team)
    await db_session.flush()
    user.team_id = team.id
    await db_session.flush()
    return team


def _lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(appconfig._CACHE, "ctf.allow_team_changes", "false")


class TestTeamChanges:
    async def test_leave(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, user = user_client
        await _put_in_team(db_session, user)

        resp = await client.post("/me/team/leave")
        assert resp.status_code == 204
        assert user.team_id is None

    async def test_leave_locked(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, user = user_client
        team = await _put_in_team(db_session, user)
        _lock(monkeypatch)

        resp = await client.post("/me/team/leave")
        assert resp.status_code == 403
        assert user.team_id == team.id

    async def test_join_locked(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, user = user_client
        db_session.add(Team(name="LockedTeam", invite_code="LOCKED12"))
        await db_session.flush()
        _lock(monkeypatch)

        resp = await client.post("/me/team/join", json={"code": "LOCKED12"})
        assert resp.status_code == 403
        assert user.team_id is None

    async def test_rotate_invite_code_locked(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, user = user_client
        team = await _put_in_team(db_session, user)
        _lock(monkeypatch)

        resp = await client.post("/me/team/invite-code")
        assert resp.status_code == 403
        assert team.invite_code == "MYTEAM01"

    async def test_create_locked(
        self,
        user_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, user = user_client
        _lock(monkeypatch)

        resp = await client.post("/me/team", json={"name": "NewTeam"})
        assert resp.status_code == 403
        assert user.team_id is None

    async def test_create_generates_invite_code(
        self,
        user_client: tuple[AsyncClient, User],
    ) -> None:
        client, _ = user_client

        resp = await client.post("/me/team", json={"name": "NewTeam"})
        assert resp.status_code == 201
        assert len(resp.json()["data"]["invite_code"]) == 8

    async def test_create_ignores_client_supplied_fields(
        self,
        user_client: tuple[AsyncClient, User],
    ) -> None:
        """Server-managed fields in the body must not reach the ORM."""
        client, _ = user_client

        resp = await client.post(
            "/me/team",
            json={"name": "NewTeam", "invite_code": "PWNED123", "bracket": "elite"},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["invite_code"] != "PWNED123"
        assert data["bracket"] is None
