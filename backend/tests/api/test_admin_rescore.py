"""Tests for re-scoring a question's submissions after an admin edit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Submission, Team, User
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

FLAG = "flag{rescore}"
_T0 = datetime.now(UTC) - timedelta(hours=1)


async def _question(
    db_session: AsyncSession, *, points: int, malus: int | None
) -> Question:
    challenge = StandardChallenge(title="Rescore", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    question = Question(
        label="Q", points=points, malus=malus, challenge_id=challenge.id
    )
    db_session.add(question)
    await db_session.flush()
    db_session.add(MatchSolution(value=FLAG, question_id=question.id))
    await db_session.flush()
    return question


async def _play(
    db_session: AsyncSession, question: Question, answers: list[str], name: str = "team"
) -> Team:
    """Record *answers* for a new team, in order, scored as the submit endpoint would."""
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    wrong = 0
    for i, answer in enumerate(answers):
        correct = answer == FLAG
        points = (
            max(0, question.points - (question.malus or 0) * wrong) if correct else 0
        )
        sub = Submission(
            answer=answer,
            is_correct=correct,
            points_earned=points,
            wrong_count_before=wrong,
            team_id=team.id,
            question_id=question.id,
        )
        db_session.add(sub)
        await db_session.flush()
        sub.created_at = _T0 + timedelta(minutes=i)
        wrong += not correct
    await db_session.flush()
    return team


async def _earned(db_session: AsyncSession, team: Team) -> int:
    rows = await db_session.scalars(
        select(Submission.points_earned).where(Submission.team_id == team.id)
    )
    return sum(rows)


async def _put(admin: AsyncClient, question: Question, **fields: object) -> None:
    resp = await admin.put(
        f"/admin/question/{question.id}", json={"id": str(question.id), **fields}
    )
    assert resp.status_code == 200


class TestQuestionEdit:
    async def test_points_change_rescores_past_solves(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        admin, _ = admin_client
        question = await _question(db_session, points=100, malus=None)
        team = await _play(db_session, question, [FLAG])

        await _put(admin, question, points=300)

        assert await _earned(db_session, team) == 300

    async def test_malus_change_rescores_past_solves(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        admin, _ = admin_client
        question = await _question(db_session, points=100, malus=10)
        team = await _play(db_session, question, ["nope", "nope", FLAG])

        await _put(admin, question, malus=25)
        assert await _earned(db_session, team) == 50

        await _put(admin, question, malus=None)
        assert await _earned(db_session, team) == 100

    async def test_unchanged_scoring_skips_the_recalculation(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        monkeypatch,
    ) -> None:
        admin, _ = admin_client
        question = await _question(db_session, points=100, malus=10)
        calls: list[object] = []

        async def _spy(*args: object) -> set[object]:
            calls.append(args)
            return set()

        monkeypatch.setattr(
            "nexctf.api.routes.admin.question.recalculate_question", _spy
        )
        await _put(admin, question, label="Renamed", points=100, malus=10)

        assert calls == []


class TestSubmissionDelete:
    async def test_deleting_a_wrong_attempt_refunds_its_malus(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        admin, _ = admin_client
        question = await _question(db_session, points=100, malus=20)
        team = await _play(db_session, question, ["nope", FLAG])
        wrong_id = await db_session.scalar(
            select(Submission.id).where(Submission.is_correct.is_(False))
        )

        resp = await admin.delete(f"/admin/submission/{wrong_id}")

        assert resp.status_code == 200
        assert await _earned(db_session, team) == 100

    async def test_deleting_the_solve_lets_a_later_answer_count(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        admin, _ = admin_client
        question = await _question(db_session, points=100, malus=None)
        team = await _play(db_session, question, [FLAG])
        solve_id = await db_session.scalar(select(Submission.id))

        resp = await admin.delete(f"/admin/submission/{solve_id}")

        assert resp.status_code == 200
        assert await _earned(db_session, team) == 0
