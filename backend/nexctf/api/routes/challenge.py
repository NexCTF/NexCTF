"""Player-facing challenge API."""

from __future__ import annotations

import asyncio
import random
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi_toolsets.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from fastapi_toolsets.schemas import Response
from nexctf.exceptions import SequentialChallengeError
from sqlalchemy import select
from sqlalchemy.orm import selectin_polymorphic, selectinload

from nexctf.api.dep import (
    CurrentUserDep,
    EventActiveDep,
    EventStartedDep,
    OptionalCurrentUserDep,
    RedisDep,
    RequireTeamDep,
    SessionDep,
)
from nexctf.module.events import emit as emit_event
from nexctf.module.scoreboard import invalidate as invalidate_scoreboard
from nexctf.module.stats import invalidate as invalidate_stats
from nexctf.core import appconfig, s3
from nexctf.util.ip import get_client_ip
from nexctf.core.rate_limit import check_rate_limit
from nexctf.model import Challenge, HintUnlock, Question, Submission, User, UserRole
from nexctf.model.solution import Solution
from nexctf.plugins.registry import solution_registry
from nexctf.schema.challenge import (
    PublicChallengeDetail,
    PublicChallengeRead,
    SubmitBody,
    SubmitResult,
)
from nexctf.schema.file import PublicFileRead
from nexctf.schema.hint import PublicHintRead
from nexctf.schema.question import PublicQuestionRead
from nexctf.schema.tag import PublicTagRead

challenge_router = APIRouter(prefix="/challenges", tags=["Challenges"])


def _check_challenge_visibility(user: User | None) -> None:
    """Raise if the current user cannot view challenges."""
    visibility = str(appconfig.get("visibility.challenges"))
    if user is not None and user.role in (UserRole.admin, UserRole.moderator):
        return
    if visibility == "hidden":
        raise ForbiddenError()
    if visibility == "authenticated" and user is None:
        raise UnauthorizedError()


def _solution_load_option():
    """Return the correct selectinload option for Question.solutions."""
    subclasses = solution_registry.polymorphic_subclasses
    if subclasses:
        return selectinload(Question.solutions).options(
            selectin_polymorphic(Solution, subclasses)
        )
    return selectinload(Question.solutions)


async def _get_active_challenge(session: SessionDep, challenge_id: UUID) -> Challenge:
    """Load a challenge with all relationships needed for the player view."""
    result = await session.execute(
        select(Challenge)
        .where(Challenge.id == challenge_id, Challenge.is_active.is_(True))
        .options(
            selectinload(Challenge.category),
            selectinload(Challenge.tags),
            selectinload(Challenge.questions).options(
                _solution_load_option(),
                selectinload(Question.hints),
                selectinload(Question.files),
                selectinload(Question.tags),
            ),
        )
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise NotFoundError(detail="Challenge not found")
    return challenge


async def _solved_ids(
    session: SessionDep, user: User | None, question_ids: list[UUID]
) -> set[UUID]:
    """Return IDs of questions already solved by the user's team."""
    if not question_ids or user is None or user.team_id is None:
        return set()
    rows = await session.execute(
        select(Submission.question_id)
        .where(
            Submission.question_id.in_(question_ids),
            Submission.is_correct.is_(True),
            Submission.team_id == user.team_id,
        )
        .distinct()
    )
    return {r[0] for r in rows}


async def _unlocked_ids(
    session: SessionDep, user: User | None, hint_ids: list[UUID]
) -> set[UUID]:
    if not hint_ids or user is None:
        return set()
    rows = await session.execute(
        select(HintUnlock.hint_id).where(
            HintUnlock.user_id == user.id,
            HintUnlock.hint_id.in_(hint_ids),
        )
    )
    return {r[0] for r in rows}


async def _question_read(
    q: Question,
    *,
    is_solved: bool,
    is_locked: bool,
    unlocked_hint_ids: set[UUID],
) -> PublicQuestionRead:
    files: list[PublicFileRead] = []
    if not is_locked:

        async def _presign(key: str) -> str:
            try:
                return await s3.presigned_view_url(key)  # type: ignore[attr-defined]
            except Exception:
                return ""

        urls = await asyncio.gather(*[_presign(f.s3_key) for f in q.files])
        files = [
            PublicFileRead(
                id=f.id,
                name=f.name,
                original_filename=f.original_filename,
                mime_type=f.mime_type,
                file_size=f.file_size,
                url=url,
            )
            for f, url in zip(q.files, urls)
        ]

    hints: list[PublicHintRead] = []
    if not is_locked:
        hints = [
            PublicHintRead(
                id=h.id,
                title=h.title,
                cost=h.cost,
                is_unlocked=h.id in unlocked_hint_ids,
                content=h.content if h.id in unlocked_hint_ids else None,
            )
            for h in sorted(q.hints, key=lambda h: h.order)
        ]

    tags = [
        PublicTagRead(id=t.id, name=t.name, description=t.description, color=t.color)
        for t in q.tags
    ]

    # Collect player-facing options from solutions that expose them (e.g. MCQ).
    # Solutions control what they expose via public_options() / is_multi_select().
    options: list[str] | None = None
    multi_select: bool = False
    if not is_locked:
        all_opts: list[str] = []
        for sol in q.solutions:
            sol_opts = sol.public_options()
            if sol_opts:
                all_opts.extend(sol_opts)
            if sol.is_multi_select():
                multi_select = True
        if all_opts:
            unique = list(set(all_opts))
            random.shuffle(unique)
            options = unique

    return PublicQuestionRead(
        id=q.id,
        label=q.label,
        description=q.description,
        points=q.points,
        malus=q.malus,
        input_type=q.input_type,
        is_solved=is_solved,
        is_locked=is_locked,
        files=files,
        hints=hints,
        tags=tags,
        options=options,
        multi_select=multi_select,
    )


@challenge_router.get("")
async def list_challenges(
    session: SessionDep,
    user: OptionalCurrentUserDep = None,
    _: EventStartedDep = None,
) -> Response[list[PublicChallengeRead]]:
    _check_challenge_visibility(user)
    result = await session.execute(
        select(Challenge)
        .where(Challenge.is_active.is_(True))
        .options(
            selectinload(Challenge.questions),
            selectinload(Challenge.category),
            selectinload(Challenge.tags),
        )
        .order_by(Challenge.title)
    )
    challenges = list(result.scalars().all())

    all_q_ids = [q.id for c in challenges for q in c.questions]
    solved = await _solved_ids(session, user, all_q_ids)

    return Response(
        data=[
            PublicChallengeRead(
                id=c.id,
                title=c.title,
                category_id=c.category_id,
                category_name=c.category_name,
                question_count=len(c.questions),
                solved_count=sum(1 for q in c.questions if q.id in solved),
                tags=[
                    PublicTagRead(
                        id=t.id, name=t.name, description=t.description, color=t.color
                    )
                    for t in c.tags
                ],
            )
            for c in challenges
        ]
    )


@challenge_router.get("/{challenge_id}")
async def get_challenge(
    session: SessionDep,
    challenge_id: UUID,
    user: OptionalCurrentUserDep = None,
    _: EventStartedDep = None,
) -> Response[PublicChallengeDetail]:
    _check_challenge_visibility(user)
    challenge = await _get_active_challenge(session, challenge_id)
    questions = sorted(challenge.questions, key=lambda q: q.index)

    solved = await _solved_ids(session, user, [q.id for q in questions])
    all_hint_ids = [h.id for q in questions for h in q.hints]
    unlocked = await _unlocked_ids(session, user, all_hint_ids)

    # Sequential: all questions are shown, but questions after the first unsolved
    # one are marked as locked (blurred on the frontend).
    locked_from: int | None = None
    if challenge.sequential:
        for i, q in enumerate(questions):
            if q.id not in solved:
                locked_from = i + 1  # everything after this index is locked
                break

    question_reads = list(
        await asyncio.gather(
            *[
                _question_read(
                    q,
                    is_solved=q.id in solved,
                    is_locked=locked_from is not None and i >= locked_from,
                    unlocked_hint_ids=unlocked,
                )
                for i, q in enumerate(questions)
            ]
        )
    )

    return Response(
        data=PublicChallengeDetail(
            id=challenge.id,
            title=challenge.title,
            description=challenge.description,
            category_id=challenge.category_id,
            category_name=challenge.category_name,
            question_count=len(questions),
            solved_count=len(solved),
            challenge_type=challenge.challenge_type,
            sequential=challenge.sequential,
            questions=question_reads,
            tags=[
                PublicTagRead(
                    id=t.id, name=t.name, description=t.description, color=t.color
                )
                for t in challenge.tags
            ],
        )
    )


@challenge_router.post("/{challenge_id}/{question_id}/submit")
async def submit_answer(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    challenge_id: UUID,
    question_id: UUID,
    obj: SubmitBody,
    user: RequireTeamDep,
    _: EventActiveDep,
) -> Response[SubmitResult]:
    _check_challenge_visibility(user)
    if appconfig.get("rate_limit.submit.enabled"):
        await check_rate_limit(
            redis,
            f"rl:submit:{user.id}",
            window_seconds=int(appconfig.get("rate_limit.submit.window_seconds")),
            max_requests=int(appconfig.get("rate_limit.submit.max_requests")),
        )

    challenge = await _get_active_challenge(session, challenge_id)

    question = next((q for q in challenge.questions if q.id == question_id), None)
    if question is None:
        raise NotFoundError(detail="Question not found in this challenge")

    solved = await _solved_ids(session, user, [question_id])
    if question_id in solved:
        return Response(
            data=SubmitResult(
                is_correct=True,
                already_solved=True,
                points_earned=0,
                message="Already solved!",
            )
        )

    if challenge.sequential:
        prev_ids = [q.id for q in challenge.questions if q.index < question.index]
        if prev_ids:
            prev_solved = await _solved_ids(session, user, prev_ids)
            if len(prev_solved) < len(prev_ids):
                raise SequentialChallengeError()

    # Count previous wrong attempts (for malus)
    wrong_rows = await session.execute(
        select(Submission.id).where(
            Submission.question_id == question_id,
            Submission.is_correct.is_(False),
            Submission.team_id == user.team_id,
        )
    )
    wrong_count_before = len(wrong_rows.all())

    answer = obj.answer
    team_id = user.team_id
    is_correct = False
    for sol in question.solutions:
        if await sol.verify(answer, team_id=team_id):
            is_correct = True
            break

    points_earned = 0
    if is_correct:
        points_earned = question.points
        if question.malus is not None:
            points_earned = max(0, points_earned - question.malus * wrong_count_before)

    await challenge.on_submit(user, question, obj.answer)

    session.add(
        Submission(
            answer=obj.answer,
            is_correct=is_correct,
            points_earned=points_earned,
            wrong_count_before=wrong_count_before,
            team_id=user.team_id,
            question_id=question_id,
        )
    )
    await session.flush()

    challenge_completed = False
    if is_correct:
        await challenge.on_solve(user, question)
        all_solved = await _solved_ids(
            session, user, [q.id for q in challenge.questions]
        )
        if len(all_solved) == len(challenge.questions):
            challenge_completed = True
            await challenge.on_complete(user)
    else:
        await challenge.on_fail(user, question, obj.answer)

    # Emit events before commit so they're part of the same transaction
    client_ip = get_client_ip(request)
    event_meta_base = {
        "challenge_title": challenge.title,
        "question_label": question.label,
    }
    if is_correct:
        await emit_event(
            session,
            redis,
            event_type="submission.correct",
            actor_id=user.id,
            target_type="challenges",
            target_id=challenge.id,
            target_label=challenge.title,
            ip=client_ip,
            meta={
                **event_meta_base,
                "team_id": str(user.team_id),
                "points_earned": points_earned,
            },
        )
        if challenge_completed:
            await emit_event(
                session,
                redis,
                event_type="challenge.complete",
                actor_id=user.id,
                target_type="challenges",
                target_id=challenge.id,
                target_label=challenge.title,
                ip=client_ip,
                meta={"team_id": str(user.team_id)},
            )
    else:
        await emit_event(
            session,
            redis,
            event_type="submission.wrong",
            actor_id=user.id,
            target_type="challenges",
            target_id=challenge.id,
            target_label=challenge.title,
            ip=client_ip,
            meta={**event_meta_base, "team_id": str(user.team_id)},
        )

    await session.commit()

    if is_correct:
        await invalidate_scoreboard(redis, user.team_id)

    return Response(
        data=SubmitResult(
            is_correct=is_correct,
            already_solved=False,
            points_earned=points_earned,
            message="Correct! 🎉" if is_correct else "Wrong answer, try again.",
        )
    )


@challenge_router.post("/{challenge_id}/{question_id}/hints/{hint_id}/unlock")
async def unlock_hint(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    challenge_id: UUID,
    question_id: UUID,
    hint_id: UUID,
    user: CurrentUserDep,
    _: EventActiveDep,
) -> Response[PublicHintRead]:
    _check_challenge_visibility(user)
    challenge = await _get_active_challenge(session, challenge_id)

    question = next((q for q in challenge.questions if q.id == question_id), None)
    if question is None:
        raise NotFoundError(detail="Question not found in this challenge")

    hint = next((h for h in question.hints if h.id == hint_id), None)
    if hint is None:
        raise NotFoundError(detail="Hint not found")

    existing = await session.execute(
        select(HintUnlock).where(
            HintUnlock.user_id == user.id,
            HintUnlock.hint_id == hint_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        session.add(HintUnlock(user_id=user.id, hint_id=hint_id, cost_paid=hint.cost))
        await session.flush()
        await challenge.on_hint_unlock(user, hint)
        await emit_event(
            session,
            redis,
            event_type="hint.unlock",
            actor_id=user.id,
            target_type="challenges",
            target_id=challenge.id,
            target_label=challenge.title,
            ip=get_client_ip(request),
            meta={
                "team_id": str(user.team_id),
                "hint_title": hint.title,
                "cost": hint.cost,
            },
        )
        await session.commit()
        await invalidate_stats(redis)

    return Response(
        data=PublicHintRead(
            id=hint.id,
            title=hint.title,
            cost=hint.cost,
            is_unlocked=True,
            content=hint.content,
        )
    )
