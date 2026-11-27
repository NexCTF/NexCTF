"""Tests for the per-team attempt limit on a question."""

from __future__ import annotations

from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Submission, User
from nexctf.model.question import Hint, Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

from ..base import get_data, make_solvable

FLAG = "NexCTF{real_flag}"
TRAP = "NexCTF{TRAP}"


async def _setup(
    db_session: AsyncSession, user: User, *, max_attempts: int | None = 2
) -> tuple[StandardChallenge, Question]:
    """Give *user* a team and a one-question challenge allowing *max_attempts*."""
    challenge, question = await make_solvable(db_session, user, FLAG)
    question.max_attempts = max_attempts
    question.trap_flags = [TRAP]
    await db_session.flush()
    return challenge, question


async def _submit(
    c: AsyncClient, challenge: StandardChallenge, question: Question, answer: str
) -> Response:
    return await c.post(
        f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": answer}
    )


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

        assert first.json()["data"]["attempts_left"] == 1
        assert second.json()["data"]["attempts_left"] == 0
        assert third.status_code == 403
        assert third.json()["error_code"] == "SUB-403-ATTEMPTS"
        assert await _submissions(db_session, question) == 2

    async def test_the_last_attempt_can_still_solve(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        await _submit(c, challenge, question, "nope")
        solved = await _submit(c, challenge, question, FLAG)

        assert solved.json()["data"]["is_correct"] is True
        assert solved.json()["data"]["attempts_left"] == 1

    async def test_a_trap_uses_an_attempt(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=1)

        await _submit(c, challenge, question, TRAP)
        refused = await _submit(c, challenge, question, FLAG)

        assert refused.json()["error_code"] == "SUB-403-ATTEMPTS"

    async def test_raising_the_limit_gives_attempts_back(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=1)
        await _submit(c, challenge, question, "nope")

        question.max_attempts = 3
        await db_session.flush()
        retry = await _submit(c, challenge, question, FLAG)

        assert retry.json()["data"]["is_correct"] is True

    async def test_no_limit_reports_no_attempts_left(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=None)

        result = await _submit(c, challenge, question, "nope")

        assert result.json()["data"]["attempts_left"] is None


async def _add_hint(db_session: AsyncSession, question: Question) -> Hint:
    hint = Hint(title="Nudge", content="look closer", cost=10, question_id=question.id)
    db_session.add(hint)
    await db_session.flush()
    return hint


async def _unlock(
    c: AsyncClient, challenge: StandardChallenge, question: Question, hint: Hint
) -> Response:
    return await c.post(
        f"/challenges/{challenge.id}/{question.id}/hints/{hint.id}/unlock"
    )


class TestHintsAfterTheLastAttempt:
    async def test_no_hint_unlocks_once_attempts_are_used_up(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=1)
        hint = await _add_hint(db_session, question)
        await _submit(c, challenge, question, "nope")

        refused = await _unlock(c, challenge, question, hint)

        assert refused.status_code == 403
        assert refused.json()["error_code"] == "SUB-403-ATTEMPTS"

    async def test_hints_unlock_while_attempts_remain(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=2)
        hint = await _add_hint(db_session, question)
        await _submit(c, challenge, question, "nope")

        unlocked = await _unlock(c, challenge, question, hint)

        assert unlocked.json()["data"]["content"] == "look closer"


class TestPlayerView:
    async def test_detail_shows_the_attempts_left(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user, max_attempts=3)
        await _submit(c, challenge, question, "nope")

        (read,) = (await get_data(c, f"/challenges/{challenge.id}"))["questions"]

        assert read["attempts_left"] == 2


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


class TestSequentialChallenge:
    async def test_running_out_of_attempts_opens_the_next_question(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """A question the team can no longer answer stops gating the next one."""
        c, user = user_client
        challenge, first = await _setup(db_session, user, max_attempts=1)
        challenge.sequential = True
        second = Question(label="Q2", index=1, challenge_id=challenge.id)
        db_session.add(second)
        await db_session.flush()
        db_session.add(MatchSolution(value="NexCTF{second}", question_id=second.id))
        await db_session.flush()

        locked = (await get_data(c, f"/challenges/{challenge.id}"))["questions"]
        await _submit(c, challenge, first, "nope")
        opened = (await get_data(c, f"/challenges/{challenge.id}"))["questions"]
        solved = await _submit(c, challenge, second, "NexCTF{second}")

        assert [q["is_locked"] for q in locked] == [False, True]
        assert [q["is_locked"] for q in opened] == [False, False]
        assert solved.json()["data"]["is_correct"] is True
