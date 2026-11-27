"""Tests for the per-team attempt limit on a question."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Submission, Team, User
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

FLAG = "NexCTF{real_flag}"
TRAP = "NexCTF{TRAP}"


async def _setup(
    db_session: AsyncSession, user: User, *, max_attempts: int | None = 2
) -> tuple[StandardChallenge, Question]:
    """Give *user* a team and a one-question challenge allowing *max_attempts*."""
    team = Team(name=f"attempts_team_{user.id.hex[:8]}")
    db_session.add(team)
    await db_session.flush()
    user.team_id = team.id

    challenge = StandardChallenge(title="Attempts", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    question = Question(
        label="Q",
        points=100,
        challenge_id=challenge.id,
        max_attempts=max_attempts,
        trap_flags=[TRAP],
    )
    db_session.add(question)
    await db_session.flush()
    db_session.add(MatchSolution(value=FLAG, question_id=question.id))
    await db_session.flush()
    return challenge, question


async def _submit(
    c: AsyncClient, challenge: StandardChallenge, question: Question, answer: str
) -> dict:
    resp = await c.post(
        f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": answer}
    )
    return {**resp.json(), "http_status": resp.status_code}


async def _submissions(db_session: AsyncSession, question: Question) -> int:
    count = await db_session.scalar(
        select(func.count()).where(Submission.question_id == question.id)
    )
    return count or 0


class TestAttemptLimit:
    async def test_wrong_answers_count_down_then_are_refused(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        first = await _submit(c, challenge, question, "nope")
        second = await _submit(c, challenge, question, "still nope")
        third = await _submit(c, challenge, question, FLAG)

        assert first["data"]["attempts_left"] == 1
        assert second["data"]["attempts_left"] == 0
        assert third["http_status"] == 403
        assert third["error_code"] == "SUB-403-ATTEMPTS"
        assert await _submissions(db_session, question) == 2

    async def test_the_last_attempt_can_still_solve(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        await _submit(c, challenge, question, "nope")
        solved = await _submit(c, challenge, question, FLAG)

        assert solved["data"]["is_correct"] is True
        assert solved["data"]["attempts_left"] == 1

    async def test_a_trap_uses_an_attempt(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=1)

        await _submit(c, challenge, question, TRAP)
        refused = await _submit(c, challenge, question, FLAG)

        assert refused["error_code"] == "SUB-403-ATTEMPTS"

    async def test_raising_the_limit_gives_attempts_back(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=1)
        await _submit(c, challenge, question, "nope")

        question.max_attempts = 3
        await db_session.flush()
        retry = await _submit(c, challenge, question, FLAG)

        assert retry["data"]["is_correct"] is True

    async def test_no_limit_reports_no_attempts_left(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=None)

        result = await _submit(c, challenge, question, "nope")

        assert result["data"]["attempts_left"] is None


class TestPlayerView:
    async def test_detail_shows_the_attempts_left(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=3)
        await _submit(c, challenge, question, "nope")

        resp = await c.get(f"/challenges/{challenge.id}")

        (read,) = resp.json()["data"]["questions"]
        assert (read["max_attempts"], read["attempts_left"]) == (3, 2)


class TestAdminValidation:
    async def test_a_limit_below_one_is_refused(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        challenge = StandardChallenge(title="Admin attempts")
        db_session.add(challenge)
        await db_session.flush()

        resp = await c.post(
            "/admin/question",
            json={"challenge_id": str(challenge.id), "label": "Q", "max_attempts": 0},
        )

        assert resp.status_code == 422
