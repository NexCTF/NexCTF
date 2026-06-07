"""Tests for scoreboard API endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Team, User, UserRole
from nexctf.model.question import Question
from nexctf.model.submission import ScoreAdjustment, Submission
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge

from ..base import NULL_UUID


async def _setup_scored_team(
    session: AsyncSession,
    team_name: str = "TeamA",
    points: int = 100,
) -> tuple[Team, StandardChallenge, Question, Submission]:
    ch = StandardChallenge(title=f"Chall-{team_name}")
    session.add(ch)
    await session.flush()

    q = Question(label="Flag", points=points, challenge_id=ch.id)
    session.add(q)
    await session.flush()

    t = Team(name=team_name)
    session.add(t)
    await session.flush()

    s = Submission(
        answer="flag{test}",
        is_correct=True,
        points_earned=points,
        wrong_count_before=0,
        team_id=t.id,
        question_id=q.id,
    )
    session.add(s)
    await session.flush()

    return t, ch, q, s


class TestGetScoreboard:
    PREFIX = "/scoreboard"

    async def test_public_access(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX)
        assert resp.status_code == 200

    async def test_empty(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX)
        data = resp.json()["data"]
        assert data["entries"] == []

    async def test_with_scored_team(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        t, _, _, _ = await _setup_scored_team(db_session)
        resp = await http_client.get(self.PREFIX)
        assert resp.status_code == 200
        entries = resp.json()["data"]["entries"]
        assert len(entries) == 1
        assert entries[0]["team_name"] == t.name
        assert entries[0]["total"] == 100
        assert entries[0]["rank"] == 1

    async def test_ranking_order(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        await _setup_scored_team(db_session, "Low", points=50)
        await _setup_scored_team(db_session, "High", points=200)
        resp = await http_client.get(self.PREFIX)
        entries = resp.json()["data"]["entries"]
        assert entries[0]["team_name"] == "High"
        assert entries[1]["team_name"] == "Low"


class TestGetScoreboardHistory:
    PREFIX = "/scoreboard/history"

    async def test_public_access(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX)
        assert resp.status_code == 200

    async def test_empty(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX)
        assert resp.json()["data"]["series"] == []

    async def test_limit_too_low(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX, params={"limit": 0})
        assert resp.status_code == 422

    async def test_limit_too_high(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX, params={"limit": 26})
        assert resp.status_code == 422

    async def test_with_data(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        t, _, _, _ = await _setup_scored_team(db_session, "HistTeam")
        resp = await http_client.get(self.PREFIX)
        series = resp.json()["data"]["series"]
        assert len(series) == 1
        assert series[0]["team_name"] == t.name
        assert series[0]["events"][0]["cumulative"] == 100

    async def test_limit_respected(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        for i in range(5):
            await _setup_scored_team(db_session, f"T{i}", points=100 + i)
        resp = await http_client.get(self.PREFIX, params={"limit": 3})
        assert len(resp.json()["data"]["series"]) == 3


class TestGetTeamScore:
    PREFIX = "/scoreboard/team"

    async def test_public_access(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        t, _, _, _ = await _setup_scored_team(db_session)
        resp = await http_client.get(f"{self.PREFIX}/{t.id}")
        assert resp.status_code == 200

    async def test_with_solves(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        t, _, _, _ = await _setup_scored_team(db_session, points=75)
        resp = await http_client.get(f"{self.PREFIX}/{t.id}")
        data = resp.json()["data"]
        assert data["total"] == 75
        assert len(data["solves"]) == 1
        assert data["adjustments"] == []

    async def test_with_adjustment(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        u = User(username="adj_admin", hashed_password="x", role=UserRole.admin)
        db_session.add(u)
        t = Team(name="AdjTeam")
        db_session.add(t)
        await db_session.flush()

        adj = ScoreAdjustment(
            amount=30, reason="bonus", team_id=t.id, created_by_id=u.id
        )
        db_session.add(adj)
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{t.id}")
        data = resp.json()["data"]
        assert data["total"] == 30
        assert data["adjustment_points"] == 30
        assert len(data["adjustments"]) == 1


class TestInvalidateScoreboard:
    PREFIX = "/admin/scoreboard/invalidate"

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.post(self.PREFIX)
        assert resp.status_code == 403

    async def test_invalidate_all(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX)
        assert resp.status_code == 200

    async def test_invalidate_by_team(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        t = Team(name="InvTeam")
        db_session.add(t)
        await db_session.flush()
        c, _ = admin_client
        resp = await c.post(self.PREFIX, params={"team_id": str(t.id)})
        assert resp.status_code == 200

    async def test_invalidate_unknown_team(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, params={"team_id": NULL_UUID})
        assert resp.status_code == 200
