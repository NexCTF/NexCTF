"""Tests for the public team profile endpoint."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Team, User

from ..base import NULL_UUID


class TestGetTeamProfile:
    PREFIX = "/team"

    async def test_not_found(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404

    async def test_profile(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        team = Team(name="ProfileTeam", country="FR", bracket="student")
        db_session.add(team)
        await db_session.flush()
        db_session.add(User(username="alice", team_id=team.id))
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{team.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "ProfileTeam"
        assert data["country"] == "FR"
        assert data["bracket"] == "student"
        assert [m["username"] for m in data["members"]] == ["alice"]

    async def test_invite_code_hidden(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        team = Team(name="SecretTeam", invite_code="ABCD1234")
        db_session.add(team)
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{team.id}")
        assert "invite_code" not in resp.json()["data"]
