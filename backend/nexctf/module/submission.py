from __future__ import annotations

from uuid import UUID

from fastapi_toolsets.db import advisory_lock
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper, selectin_polymorphic, selectinload

from nexctf.exceptions import SolutionTimeoutError
from nexctf.model import Question, Submission
from nexctf.model.solution import Solution
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
    for in-flight submits and holds new ones until it commits.
    """
    async with advisory_lock(
        session,
        question_id.int & _BIGINT_MASK,
        shared=shared,
        xact=True,
        timeout=timeout,
    ):
        pass


async def recalculate_question(
    session: AsyncSession,
    redis: Redis,
    question_id: UUID,
) -> set[UUID]:
    """Re-verify every submission to *question_id*, then commit and drop the caches."""
    question = await _load_question(session, question_id)
    if question is None:
        raise ValueError(f"Question {question_id} not found")

    await lock_question(session, question_id, timeout=_RECALC_LOCK_TIMEOUT)
    submissions = (
        (
            await session.execute(
                select(Submission)
                .where(Submission.question_id == question_id)
                .order_by(Submission.created_at)
            )
        )
        .scalars()
        .all()
    )

    wrong_count_by_team: dict[UUID, int] = {}
    solved_teams: set[UUID] = set()
    affected_teams: set[UUID] = set()
    timed_out_solutions: set[UUID] = set()

    for sub in submissions:
        team_id = sub.team_id
        wrong_before = wrong_count_by_team.get(team_id, 0)

        new_is_trap = question.is_trap(sub.answer)

        new_is_correct = False
        if not new_is_trap:
            for sol in question.solutions:
                try:
                    if await sol.verify(sub.answer, team_id=team_id):
                        new_is_correct = True
                        break
                except SolutionTimeoutError as exc:
                    if (
                        exc.solution_id is not None
                        and exc.solution_id not in timed_out_solutions
                    ):
                        timed_out_solutions.add(exc.solution_id)
                        await emit(
                            session,
                            redis,
                            event_type="solution.timeout",
                            target_type="questions",
                            target_id=question_id,
                            target_label=question.label,
                            meta={
                                "solution_id": str(exc.solution_id),
                                "team_id": str(team_id),
                                "context": "recalculation",
                            },
                        )

        if new_is_correct and team_id not in solved_teams:
            new_points = max(0, question.points - (question.malus or 0) * wrong_before)
            solved_teams.add(team_id)
        else:
            new_points = 0

        if not new_is_correct:
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

    await session.commit()
    await invalidate(redis)
    for tid in affected_teams:
        await invalidate_team(redis, tid)

    return affected_teams


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
        .options(
            selectinload(Question.solutions).options(
                selectin_polymorphic(Solution, solution_subtypes)
            ),
            selectin_polymorphic(Question, question_subtypes),
            *choices_opts,
        )
    )
