"""Player-facing challenge API."""

from __future__ import annotations

import random
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi_toolsets.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from fastapi_toolsets.schemas import Response
from nexctf.exceptions import SequentialChallengeError, SolutionTimeoutError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from nexctf.api.dep import (
    CurrentUserDep,
    EventActiveDep,
    EventStartedDep,
    OptionalCurrentUserDep,
    RedisDep,
    RequireTeamDep,
    SessionDep,
)
from nexctf.module.challenge import get_detail_structure, get_list_structure
from nexctf.module.challenge.compute import QuestionStructure, solution_load_option
from nexctf.module.events import emit as emit_event
from nexctf.module.scoreboard import invalidate as invalidate_scoreboard
from nexctf.module.stats import invalidate as invalidate_stats
from nexctf.module.stats import invalidate_team
from nexctf.core import appconfig
from nexctf.util.ip import get_client_ip
from nexctf.core.rate_limit import check_rate_limit
from nexctf.model import Challenge, HintUnlock, Question, Submission, User, UserRole
from nexctf.schema.challenge import (
    PublicChallengeDetail,
    PublicChallengeRead,
    SubmitBody,
    SubmitResult,
)
from nexctf.schema.file import PublicFileRead
from nexctf.schema.hint import PublicHintRead
from nexctf.schema.question import PublicQuestionRead
from nexctf.util.datetime import is_config_dt_past

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


async def _get_active_challenge(session: SessionDep, challenge_id: UUID) -> Challenge:
    """Load a challenge with all relationships needed for the player view."""
    result = await session.execute(
        select(Challenge)
        .where(Challenge.id == challenge_id, Challenge.is_active.is_(True))
        .options(
            selectinload(Challenge.category),
            selectinload(Challenge.tags),
            selectinload(Challenge.questions).options(
                solution_load_option(),
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


def _writeup_visible(*, challenge_completed: bool) -> bool:
    """A writeup shows once the team completes the challenge, or once the CTF
    ends if the admin opted to release writeups after the event."""
    if challenge_completed:
        return True
    return bool(appconfig.get("ctf.release_writeups_after_end")) and is_config_dt_past(
        "ctf.end_time"
    )


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


def _assemble_question(
    q: QuestionStructure,
    *,
    is_solved: bool,
    is_locked: bool,
    unlocked_hint_ids: set[UUID],
) -> PublicQuestionRead:
    """Build a player question view from cached structure + per-user state.

    Locked questions hide their files, hints and options (the frontend blurs
    them); option order is shuffled per request.
    """
    files: list[PublicFileRead] = [] if is_locked else list(q.files)

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
            for h in q.hints
        ]

    options: list[str] | None = None
    if not is_locked and q.options:
        options = list(q.options)
        random.shuffle(options)

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
        tags=list(q.tags),
        options=options,
        multi_select=q.multi_select,
    )


@challenge_router.get("")
async def list_challenges(
    session: SessionDep,
    redis: RedisDep,
    user: OptionalCurrentUserDep = None,
    _: EventStartedDep = None,
) -> Response[list[PublicChallengeRead]]:
    _check_challenge_visibility(user)
    structure = await get_list_structure(session, redis)

    all_q_ids = [qid for item in structure for qid in item.question_ids]
    solved = await _solved_ids(session, user, all_q_ids)

    return Response(
        data=[
            PublicChallengeRead(
                id=item.id,
                title=item.title,
                category_id=item.category_id,
                category_name=item.category_name,
                question_count=len(item.question_ids),
                solved_count=sum(1 for qid in item.question_ids if qid in solved),
                tags=list(item.tags),
            )
            for item in structure
        ]
    )


@challenge_router.get("/{challenge_id}")
async def get_challenge(
    session: SessionDep,
    redis: RedisDep,
    challenge_id: UUID,
    user: OptionalCurrentUserDep = None,
    _: EventStartedDep = None,
) -> Response[PublicChallengeDetail]:
    _check_challenge_visibility(user)
    structure = await get_detail_structure(session, redis, challenge_id)
    questions = structure.questions

    solved = await _solved_ids(session, user, [q.id for q in questions])
    all_hint_ids = [h.id for q in questions for h in q.hints]
    unlocked = await _unlocked_ids(session, user, all_hint_ids)

    # Sequential: all questions are shown, but questions after the first unsolved
    # one are marked as locked (blurred on the frontend).
    locked_from: int | None = None
    if structure.sequential:
        for i, q in enumerate(questions):
            if q.id not in solved:
                locked_from = i + 1  # everything after this index is locked
                break

    question_reads = [
        _assemble_question(
            q,
            is_solved=q.id in solved,
            is_locked=locked_from is not None and i >= locked_from,
            unlocked_hint_ids=unlocked,
        )
        for i, q in enumerate(questions)
    ]

    challenge_completed = len(questions) > 0 and len(solved) == len(questions)
    writeup = (
        structure.writeup
        if _writeup_visible(challenge_completed=challenge_completed)
        else None
    )

    return Response(
        data=PublicChallengeDetail(
            id=structure.id,
            title=structure.title,
            description=structure.description,
            writeup=writeup,
            category_id=structure.category_id,
            category_name=structure.category_name,
            question_count=len(questions),
            solved_count=len(solved),
            challenge_type=structure.challenge_type,
            sequential=structure.sequential,
            questions=question_reads,
            tags=list(structure.tags),
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
    timed_out: list[SolutionTimeoutError] = []
    for sol in question.solutions:
        try:
            if await sol.verify(answer, team_id=team_id):
                is_correct = True
                break
        except SolutionTimeoutError as exc:
            timed_out.append(exc)

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
    for exc in timed_out:
        await emit_event(
            session,
            redis,
            event_type="solution.timeout",
            actor_id=user.id,
            target_type="challenges",
            target_id=challenge.id,
            target_label=challenge.title,
            ip=client_ip,
            meta={
                **event_meta_base,
                "team_id": str(user.team_id),
                "solution_id": str(exc.solution_id),
                "submission": answer[:200],
            },
        )
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
    # Any submission (right or wrong) changes the team's per-challenge stats.
    await invalidate_team(redis, user.team_id)

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
