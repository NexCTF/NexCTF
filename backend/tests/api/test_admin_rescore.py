"""Tests for re-scoring a question's submissions after an admin edit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import Table, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.exceptions import SolutionTimeoutError
from nexctf.model import Event, Submission, Team, User
from nexctf.model.question import Question
from nexctf.module import submission as submission_module
from nexctf.module.submission import recalculate_question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

from ..base import put_in_team

FLAG = "flag{rescore}"
NEW_FLAG = "flag{rescore-v2}"
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
            correct_at_submit=correct,
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


async def _set_flag(
    admin: AsyncClient, db_session: AsyncSession, question: Question, value: str
) -> None:
    """Replace the question's only flag through the admin API."""
    sol_id = str(
        await db_session.scalar(
            select(MatchSolution.id).where(MatchSolution.question_id == question.id)
        )
    )
    resp = await admin.put(
        f"/admin/solution/{sol_id}", json={"id": sol_id, "value": value}
    )
    assert resp.status_code == 200, resp.text


async def _verdicts(
    db_session: AsyncSession, question: Question
) -> list[tuple[str, bool, int, int]]:
    rows = await db_session.execute(
        select(
            Submission.answer,
            Submission.is_correct,
            Submission.wrong_count_before,
            Submission.points_earned,
        )
        .where(Submission.question_id == question.id)
        .order_by(Submission.created_at)
    )
    return [tuple(r) for r in rows]


class TestFlagChange:
    async def test_a_new_flag_moves_the_solve_to_the_team_that_sent_it(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        admin, _ = admin_client
        question = await _question(db_session, points=100, malus=None)
        old = await _play(db_session, question, [FLAG], name="old")
        new = await _play(db_session, question, [NEW_FLAG], name="new")

        await _set_flag(admin, db_session, question, NEW_FLAG)

        assert await _earned(db_session, old) == 0
        assert await _earned(db_session, new) == 100

    async def test_a_rescore_audits_the_solves_it_moved(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        admin, admin_user = admin_client
        question = await _question(db_session, points=100, malus=None)
        old = await _play(db_session, question, [FLAG], name="old")
        new = await _play(db_session, question, [NEW_FLAG], name="new")

        await _set_flag(admin, db_session, question, NEW_FLAG)
        await _set_flag(admin, db_session, question, NEW_FLAG)

        events = (
            await db_session.scalars(
                select(Event).where(Event.event_type == "question.rescored")
            )
        ).all()
        assert len(events) == 1
        assert events[0].target_id == question.id
        assert events[0].actor_id == admin_user.id
        assert events[0].meta == {
            "teams_changed": 2,
            "solves_granted": [str(new.id)],
            "solves_revoked": [str(old.id)],
        }

    async def test_a_revoked_solve_does_not_use_an_attempt(
        self,
        admin_client: tuple[AsyncClient, User],
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        admin, _ = admin_client
        c, user = user_client
        await put_in_team(db_session, user)
        question = await _question(db_session, points=100, malus=10)
        question.max_attempts = 3
        await db_session.flush()
        url = f"/challenges/{question.challenge_id}/{question.id}/submit"
        for answer in ("nope", "still nope", FLAG):
            await c.post(url, json={"answer": answer})

        await _set_flag(admin, db_session, question, NEW_FLAG)
        resp = await c.post(url, json={"answer": NEW_FLAG})
        await _put(admin, question, points=200)

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["is_correct"] is True
        assert await _verdicts(db_session, question) == [
            ("nope", False, 0, 0),
            ("still nope", False, 1, 0),
            (FLAG, False, 2, 0),
            (NEW_FLAG, True, 2, 180),
        ]


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


class TestRecalculationTimeout:
    async def test_a_timeout_keeps_the_recorded_solve(
        self, db_session: AsyncSession, mock_redis, monkeypatch
    ) -> None:
        question = await _question(db_session, points=100, malus=None)
        team = await _play(db_session, question, [FLAG])

        async def _slow(self: MatchSolution, *_a: object, **_kw: object) -> bool:
            raise SolutionTimeoutError(self.id, self.value)

        monkeypatch.setattr(MatchSolution, "verify", _slow)
        await recalculate_question(db_session, mock_redis, question.id)

        assert await _earned(db_session, team) == 100

    async def test_a_timeout_keeps_a_wrong_answer_wrong(
        self, db_session: AsyncSession, mock_redis, monkeypatch
    ) -> None:
        question = await _question(db_session, points=100, malus=None)
        team = await _play(db_session, question, ["nope"])

        async def _slow(self: MatchSolution, *_a: object, **_kw: object) -> bool:
            raise SolutionTimeoutError(self.id, self.value)

        monkeypatch.setattr(MatchSolution, "verify", _slow)
        await recalculate_question(db_session, mock_redis, question.id)

        assert await _earned(db_session, team) == 0


class TestLockTimeout:
    async def test_the_lock_timeout_ends_with_the_wait(
        self, db_session: AsyncSession
    ) -> None:
        from nexctf.module.submission import lock_question

        before = await db_session.scalar(text("SHOW lock_timeout"))
        question = await _question(db_session, points=100, malus=None)

        await lock_question(db_session, question.id, timeout="5s")

        assert await db_session.scalar(text("SHOW lock_timeout")) == before


class TestRecalculationLock:
    async def test_answers_are_checked_before_the_lock_and_late_ones_under_it(
        self, db_session: AsyncSession, mock_redis, monkeypatch
    ) -> None:
        question = await _question(db_session, points=100, malus=None)
        await _play(db_session, question, ["nope", "still nope"])
        late = Team(name="late")
        db_session.add(late)
        await db_session.flush()
        checked: list[str] = []
        verify = MatchSolution.verify
        lock = submission_module.lock_question

        async def _spy(self: MatchSolution, answer: str, **kw: object) -> bool:
            checked.append(answer)
            return await verify(self, answer, **kw)

        async def _lock(session: AsyncSession, question_id: UUID, **_: object) -> None:
            assert checked == ["nope", "still nope"]
            session.add(
                Submission(answer=FLAG, team_id=late.id, question_id=question.id)
            )
            await session.flush()
            await lock(session, question_id)

        monkeypatch.setattr(MatchSolution, "verify", _spy)
        monkeypatch.setattr(submission_module, "lock_question", _lock)
        await recalculate_question(db_session, mock_redis, question.id)

        assert checked == ["nope", "still nope", FLAG]
        assert await _earned(db_session, late) == 100

    async def test_a_flag_changed_while_waiting_rechecks_every_answer(
        self, db_session: AsyncSession, mock_redis, monkeypatch
    ) -> None:
        question = await _question(db_session, points=100, malus=None)
        team = await _play(db_session, question, [NEW_FLAG])
        sol_id = await db_session.scalar(
            select(MatchSolution.id).where(MatchSolution.question_id == question.id)
        )
        match = cast(Table, MatchSolution.__table__)
        lock = submission_module.lock_question

        async def _lock(session: AsyncSession, question_id: UUID, **_: object) -> None:
            await session.execute(
                update(match).where(match.c.id == sol_id).values(value=NEW_FLAG)
            )
            await lock(session, question_id)

        monkeypatch.setattr(submission_module, "lock_question", _lock)
        await recalculate_question(db_session, mock_redis, question.id)

        assert await _earned(db_session, team) == 100
