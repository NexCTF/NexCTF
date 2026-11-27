from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple
from uuid import UUID

from fastapi_toolsets.db import advisory_lock
from redis.asyncio import Redis
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper, selectin_polymorphic, selectinload

from nexctf.exceptions import SolutionTimeoutError
from nexctf.model import Question, Submission
from nexctf.model.solution import Solution
from nexctf.module.audit import audit_actor
from nexctf.module.events import emit
from nexctf.module.scoreboard import invalidate
from nexctf.module.stats import invalidate_team

_BIGINT_MASK = 0x7FFF_FFFF_FFFF_FFFF
_RECALC_LOCK_TIMEOUT = "5s"


async def lock_question(
    session: AsyncSession,
    question_id: UUID,
    *,
    shared: bool = False,
    timeout: str | None = None,
) -> None:
    """Hold a transaction lock on *question_id*.

    Submits take it shared, a recalculation exclusive, so a recalculation waits
    for in-flight submits and holds new ones until it commits. A *timeout*
    bounds only this wait, not the rest of the transaction.
    """
    async with advisory_lock(
        session,
        question_id.int & _BIGINT_MASK,
        shared=shared,
        xact=True,
        timeout=timeout,
    ):
        pass
    if timeout is not None:
        await session.execute(text("SET LOCAL lock_timeout = DEFAULT"))


async def recalculate_question(
    session: AsyncSession,
    redis: Redis,
    question_id: UUID,
) -> set[UUID]:
    """Re-verify every submission to *question_id*, then commit and drop the caches."""
    affected_teams = await rescore_question(session, redis, question_id)
    await session.commit()
    await invalidate_scores(redis, affected_teams)
    return affected_teams


async def invalidate_scores(redis: Redis, team_ids: set[UUID]) -> None:
    """Drop the scoreboard and the stats of the teams a rescore changed."""
    await invalidate(redis)
    for tid in team_ids:
        await invalidate_team(redis, tid)


class _Verdict(NamedTuple):
    is_trap: bool
    is_correct: bool
    timed_out: bool


class _Checker:
    """Verifies a question's submissions once each, auditing every timed-out solution."""

    def __init__(
        self, session: AsyncSession, redis: Redis | None, question: Question
    ) -> None:
        self.session = session
        self.redis = redis
        self.question = question
        self.verdicts: dict[UUID, _Verdict] = {}
        self.timed_out_solutions: set[UUID] = set()

    async def check(self, submissions: Sequence[Submission]) -> None:
        """Verify the *submissions* not verified yet."""
        for sub in submissions:
            if sub.id not in self.verdicts:
                self.verdicts[sub.id] = await self._verify(sub)

    async def _verify(self, sub: Submission) -> _Verdict:
        if self.question.is_trap(sub.answer):
            return _Verdict(is_trap=True, is_correct=False, timed_out=False)
        timed_out = False
        for sol in self.question.solutions:
            try:
                if await sol.verify(sub.answer, team_id=sub.team_id):
                    return _Verdict(is_trap=False, is_correct=True, timed_out=False)
            except SolutionTimeoutError as exc:
                timed_out = True
                await self._emit_timeout(exc, sub.team_id)
        return _Verdict(is_trap=False, is_correct=False, timed_out=timed_out)

    async def _emit_timeout(self, exc: SolutionTimeoutError, team_id: UUID) -> None:
        if exc.solution_id is None or exc.solution_id in self.timed_out_solutions:
            return
        self.timed_out_solutions.add(exc.solution_id)
        await emit(
            self.session,
            self.redis,
            event_type="solution.timeout",
            target_type="questions",
            target_id=self.question.id,
            target_label=self.question.label,
            meta={
                "solution_id": str(exc.solution_id),
                "team_id": str(team_id),
                "context": "recalculation",
            },
        )


def _answer_key(question: Question) -> tuple[frozenset[str], dict[UUID, tuple]]:
    """What decides a verdict: the trap flags and every solution's columns."""
    return (
        frozenset(flag.casefold() for flag in question.trap_flags),
        {
            sol.id: tuple(
                getattr(sol, attr.key) for attr in sa_inspect(sol).mapper.column_attrs
            )
            for sol in question.solutions
        },
    )


async def _submissions(
    session: AsyncSession, question_id: UUID
) -> Sequence[Submission]:
    result = await session.scalars(
        select(Submission)
        .where(Submission.question_id == question_id)
        .order_by(Submission.created_at)
        .execution_options(populate_existing=True)
    )
    return result.all()


async def rescore_question(
    session: AsyncSession,
    redis: Redis | None,
    question_id: UUID,
    *,
    lock_timeout: str | None = _RECALC_LOCK_TIMEOUT,
) -> set[UUID]:
    """Re-verify every submission to *question_id* inside the open transaction.

    Answers are checked before the exclusive lock is taken; under it only the
    submissions that arrived meanwhile are, or every one if the question's flags
    changed meanwhile. Returns the teams whose submissions changed; the caller
    commits.
    """
    question = await _load_question(session, question_id)
    if question is None:
        raise ValueError(f"Question {question_id} not found")

    answer_key = _answer_key(question)
    checker = _Checker(session, redis, question)
    await checker.check(await _submissions(session, question_id))
    await lock_question(session, question_id, timeout=lock_timeout)
    question = await _load_question(session, question_id)
    if question is None:
        raise ValueError(f"Question {question_id} not found")
    if _answer_key(question) != answer_key:
        checker.verdicts.clear()
    submissions = await _submissions(session, question_id)
    await checker.check(submissions)

    solved_before = {sub.team_id for sub in submissions if sub.is_correct}
    wrong_count_by_team: dict[UUID, int] = {}
    solved_teams: set[UUID] = set()
    affected_teams: set[UUID] = set()

    for sub in submissions:
        team_id = sub.team_id
        wrong_before = wrong_count_by_team.get(team_id, 0)
        verdict = checker.verdicts[sub.id]
        new_is_trap = verdict.is_trap
        new_is_correct = verdict.is_correct or (verdict.timed_out and sub.is_correct)

        if new_is_correct and team_id not in solved_teams:
            new_points = max(0, question.points - (question.malus or 0) * wrong_before)
            solved_teams.add(team_id)
        else:
            new_points = 0

        if not new_is_correct and not sub.correct_at_submit:
            wrong_count_by_team[team_id] = wrong_before + 1

        if (
            sub.is_correct != new_is_correct
            or sub.wrong_count_before != wrong_before
            or sub.points_earned != new_points
            or sub.is_trap != new_is_trap
        ):
            sub.is_correct = new_is_correct
            sub.wrong_count_before = wrong_before
            sub.points_earned = new_points
            sub.is_trap = new_is_trap
            affected_teams.add(team_id)

    await session.flush()
    if affected_teams:
        await _emit_rescored(
            session,
            redis,
            question,
            affected=affected_teams,
            granted=solved_teams - solved_before,
            revoked=solved_before - solved_teams,
        )
    return affected_teams


async def _emit_rescored(
    session: AsyncSession,
    redis: Redis | None,
    question: Question,
    *,
    affected: set[UUID],
    granted: set[UUID],
    revoked: set[UUID],
) -> None:
    """Audit one rescore: the teams it changed, and the solves it granted or revoked."""
    actor_id, ip = audit_actor()
    await emit(
        session,
        redis,
        event_type="question.rescored",
        actor_id=actor_id,
        ip=ip,
        target_type="questions",
        target_id=question.id,
        target_label=question.label,
        meta={
            "teams_changed": len(affected),
            "solves_granted": sorted(str(t) for t in granted),
            "solves_revoked": sorted(str(t) for t in revoked),
        },
    )


def _subclasses(base: type) -> list[type]:
    return [
        d.class_
        for d in class_mapper(base).self_and_descendants
        if d.class_ is not base
    ]


async def _load_question(session: AsyncSession, question_id: UUID) -> Question | None:
    solution_subtypes = _subclasses(Solution)
    question_subtypes = _subclasses(Question)

    choices_opts = [
        selectinload(getattr(sub, "choices"))  # noqa: B009
        for sub in question_subtypes
        if hasattr(sub, "choices")
    ]

    return await session.scalar(
        select(Question)
        .where(Question.id == question_id)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Question.solutions).options(
                selectin_polymorphic(Solution, solution_subtypes)
            ),
            selectin_polymorphic(Question, question_subtypes),
            *choices_opts,
        )
    )
