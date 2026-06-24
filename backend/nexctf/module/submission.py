from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi_toolsets.db import LockMode, lock_tables
from redis.asyncio import Redis
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectin_polymorphic, selectinload

from nexctf.core.db import async_session_maker
from nexctf.exceptions import SolutionTimeoutError
from nexctf.model import Question, Submission
from nexctf.model.solution import Solution
from nexctf.module.events import emit
from nexctf.module.scoreboard import invalidate
from nexctf.module.stats import invalidate_team


async def recalculate_question(
    session: AsyncSession,
    redis: Redis,
    question_id: UUID,
) -> set[UUID]:
    question = await _load_question(session, question_id)
    if question is None:
        raise ValueError(f"Question {question_id} not found")

    async with lock_tables(
        session_maker=async_session_maker, tables=[Submission], mode=LockMode.EXCLUSIVE
    ) as locked:
        submissions = (
            (
                await locked.execute(
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

            new_is_correct = False
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
                new_points = max(
                    0, question.points - (question.malus or 0) * wrong_before
                )
                solved_teams.add(team_id)
            else:
                new_points = 0

            if not new_is_correct:
                wrong_count_by_team[team_id] = wrong_before + 1

            if (
                sub.is_correct != new_is_correct
                or sub.wrong_count_before != wrong_before
                or sub.points_earned != new_points
            ):
                sub.is_correct = new_is_correct
                sub.wrong_count_before = wrong_before
                sub.points_earned = new_points
                affected_teams.add(team_id)

    await asyncio.gather(
        *[invalidate(redis, tid) for tid in affected_teams],
        *[invalidate_team(redis, tid) for tid in affected_teams],
    )

    return affected_teams


def _subclasses(base: type) -> list[type]:
    return [
        d.class_ for d in sa_inspect(base).self_and_descendants if d.class_ is not base
    ]


async def _load_question(session: AsyncSession, question_id: UUID) -> Question | None:
    solution_subtypes = _subclasses(Solution)
    question_subtypes = _subclasses(Question)

    choices_opts = [
        selectinload(getattr(sub, "choices"))
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
