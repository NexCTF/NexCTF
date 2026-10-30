"""Tests for disqualifying a team: out of the rankings and unable to play."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Submission, Team, User
from nexctf.model.event import Event
from nexctf.model.question import Hint, Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from tests.base import make_solvable

FLAG = "flag{dq}"


async def _scored(db_session: AsyncSession, name: str, points: int) -> Team:
    """Create a team holding one correct submission worth *points*."""
    team = Team(name=name)
    challenge = StandardChallenge(title=f"chall_{name}", is_active=True)
    db_session.add_all([team, challenge])
    await db_session.flush()
    question = Question(label="Q", points=points, challenge_id=challenge.id)
    db_session.add(question)
    await db_session.flush()
    db_session.add(
        Submission(
            answer=FLAG,
            is_correct=True,
            points_earned=points,
            team_id=team.id,
            question_id=question.id,
        )
    )
    await db_session.flush()
    return team


async def _disqualify(admin: AsyncClient, team: Team, value: bool = True) -> None:
    resp = await admin.put(
        f"/admin/team/{team.id}", json={"id": str(team.id), "is_disqualified": value}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_disqualified"] is value


class TestRankings:
    async def test_disqualified_team_leaves_the_scoreboard(
        self,
        admin_client: tuple[AsyncClient, User],
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        admin, _ = admin_client
        cheater = await _scored(db_session, "cheater", 500)
        honest = await _scored(db_session, "honest", 100)

        await _disqualify(admin, cheater)

        entries = (await http_client.get("/scoreboard")).json()["data"]["entries"]
        assert [(e["team_id"], e["rank"]) for e in entries] == [(str(honest.id), 1)]
        series = (await http_client.get("/scoreboard/history")).json()["data"]["series"]
        assert [s["team_id"] for s in series] == [str(honest.id)]
        admin_entries = (await admin.get("/admin/scoreboard")).json()["data"]["entries"]
        assert [e["team_id"] for e in admin_entries] == [str(honest.id)]

    async def test_reinstated_team_is_ranked_again(
        self,
        admin_client: tuple[AsyncClient, User],
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        admin, _ = admin_client
        team = await _scored(db_session, "reinstated", 100)

        await _disqualify(admin, team)
        await _disqualify(admin, team, False)

        entries = (await http_client.get("/scoreboard")).json()["data"]["entries"]
        assert [e["team_id"] for e in entries] == [str(team.id)]

    async def test_profile_flags_the_team_without_a_rank(
        self,
        admin_client: tuple[AsyncClient, User],
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        admin, _ = admin_client
        team = await _scored(db_session, "flagged", 100)

        await _disqualify(admin, team)

        data = (await http_client.get(f"/team/{team.id}")).json()["data"]
        assert data["is_disqualified"] is True
        assert data["rank"] is None

    async def test_disqualification_is_audited(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        admin, admin_user = admin_client
        team = await _scored(db_session, "audited", 100)

        await _disqualify(admin, team)
        await _disqualify(admin, team, False)
        await _disqualify(admin, team, False)

        rows = (
            await db_session.execute(
                select(Event.event_type, Event.actor_id)
                .where(Event.target_id == team.id)
                .order_by(Event.created_at)
            )
        ).all()
        assert [tuple(r) for r in rows] == [
            ("admin.team_disqualified", admin_user.id),
            ("admin.team_reinstated", admin_user.id),
        ]


class TestPlay:
    async def test_disqualified_team_cannot_submit(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, user = user_client
        challenge, question = await make_solvable(db_session, user, FLAG)
        team = await db_session.get_one(Team, user.team_id)
        team.is_disqualified = True
        await db_session.flush()

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": FLAG}
        )

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-DISQUALIFIED"
        assert await db_session.scalar(select(Submission.id)) is None

    async def test_disqualified_team_cannot_unlock_hints(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, user = user_client
        challenge, question = await make_solvable(db_session, user, FLAG)
        hint = Hint(title="H", content="secret", cost=10, question_id=question.id)
        db_session.add(hint)
        team = await db_session.get_one(Team, user.team_id)
        team.is_disqualified = True
        await db_session.flush()

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/hints/{hint.id}/unlock"
        )

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-DISQUALIFIED"
