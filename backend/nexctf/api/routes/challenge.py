"""Player-facing challenge API."""

from __future__ import annotations

import asyncio
import random
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import Response
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.api.dep import (
    ConfigDep,
    EventActiveDep,
    EventStartedDep,
    OptionalCurrentUserDep,
    RedisDep,
    RequireTeamDep,
    SessionDep,
    check_visibility,
)
from nexctf.core import appconfig
from nexctf.core.rate_limit import check_config_rate_limit
from nexctf.exceptions import (
    ChallengeNotCompletedError,
    FeedbackDisabledError,
    QuestionBlockedError,
    SequentialChallengeError,
    SolutionTimeoutError,
)
from nexctf.model import (
    Challenge,
    ChallengeFeedback,
    HintUnlock,
    Question,
    Submission,
    User,
)
from nexctf.module.challenge import get_detail_structure, get_list_structure
from nexctf.module.challenge.compute import QuestionStructure, solution_load_option
from nexctf.module.events import emit as emit_event
from nexctf.module.scoreboard import invalidate as invalidate_scoreboard
from nexctf.module.stats import invalidate as invalidate_stats
from nexctf.module.stats import invalidate_team
from nexctf.schema.challenge import (
    PublicChallengeDetail,
    PublicChallengeRead,
    SubmitBody,
    SubmitResult,
)
from nexctf.schema.feedback import FeedbackBody, FeedbackUpsert, PublicFeedbackRead
from nexctf.schema.file import PublicFileRead
from nexctf.schema.hint import PublicHintRead
from nexctf.schema.question import PublicQuestionRead
from nexctf.util.async_utils import dispatch_hook
from nexctf.util.datetime import is_config_dt_past
from nexctf.util.ip import get_client_ip

challenge_router = APIRouter(prefix="/challenges", tags=["Challenges"])


def _check_challenge_visibility(user: User | None, overrides: dict[str, str]) -> None:
    """Raise if the current user cannot view challenges."""
    check_visibility(user, overrides, "visibility.challenges")


async def _get_active_challenge(session: SessionDep, challenge_id: UUID) -> Challenge:
    """Load a challenge with all relationships needed for the player view."""
    result = await session.execute(
        select(Challenge)
        .where(Challenge.id == challenge_id, Challenge.is_active.is_(True))
        .options(
            selectinload(Challenge.questions).options(
                solution_load_option(),
                selectinload(Question.hints),
                selectinload(Question.files),
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


async def _blocked_ids(
    session: SessionDep, user: User | None, question_ids: list[UUID]
) -> set[UUID]:
    """Return IDs of questions the user's team blocked by hitting a trap flag."""
    if not question_ids or user is None or user.team_id is None:
        return set()
    rows = await session.execute(
        select(Submission.question_id)
        .where(
            Submission.question_id.in_(question_ids),
            Submission.is_trap.is_(True),
            Submission.team_id == user.team_id,
        )
        .distinct()
    )
    return {r[0] for r in rows}


async def _check_question_access(
    session: SessionDep, user: User, challenge: Challenge, question: Question
) -> None:
    """Raise if the team may not act on *question*: blocked by a trap, or still
    locked behind unsolved earlier questions."""
    if question.trap_flags and await _blocked_ids(session, user, [question.id]):
        raise QuestionBlockedError()
    if not challenge.sequential:
        return
    prev_ids = [q.id for q in challenge.questions if q.index < question.index]
    if len(await _solved_ids(session, user, prev_ids)) < len(prev_ids):
        raise SequentialChallengeError()


def _writeup_visible(*, challenge_completed: bool, overrides: dict[str, str]) -> bool:
    """A writeup shows once the team completes the challenge, or once the CTF
    ends if the admin opted to release writeups after the event."""
    if challenge_completed:
        return True
    return bool(
        appconfig.get_with_overrides("ctf.release_writeups_after_end", overrides)
    ) and is_config_dt_past("ctf.end_time", overrides)


def _feedback_enabled(overrides: dict[str, str]) -> bool:
    return bool(
        appconfig.get_with_overrides("ctf.enable_challenge_feedback", overrides)
    )


async def _my_feedback(
    session: SessionDep, user: User, challenge_id: UUID
) -> PublicFeedbackRead | None:
    """Return the caller's team feedback on *challenge_id*, if any."""
    if user.team_id is None:
        return None
    feedback = await crud.ChallengeFeedbackCrud.first(
        session=session,
        filters=[
            ChallengeFeedback.team_id == user.team_id,
            ChallengeFeedback.challenge_id == challenge_id,
        ],
    )
    return PublicFeedbackRead.model_validate(feedback) if feedback else None


async def _unlocked_ids(
    session: SessionDep, user: User | None, hint_ids: list[UUID]
) -> set[UUID]:
    """Return the hints among *hint_ids* the caller's team has unlocked."""
    if not hint_ids or user is None or user.team_id is None:
        return set()
    rows = await session.execute(
        select(HintUnlock.hint_id).where(
            HintUnlock.team_id == user.team_id,
            HintUnlock.hint_id.in_(hint_ids),
        )
    )
    return {r[0] for r in rows}


def _assemble_question(
    q: QuestionStructure,
    *,
    is_solved: bool,
    is_locked: bool,
    is_blocked: bool,
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
        is_blocked=is_blocked,
        has_trap=q.has_trap,
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
    overrides: ConfigDep,
    user: OptionalCurrentUserDep = None,
    _: EventStartedDep = None,
) -> Response[list[PublicChallengeRead]]:
    _check_challenge_visibility(user, overrides)
    structure = await get_list_structure(session, redis)

    all_q_ids = [qid for item in structure for qid in item.question_ids]
    solved = await _solved_ids(session, user, all_q_ids)

    return Response(
        data=[
            PublicChallengeRead(
                id=item.id,
                title=item.title,
                category=item.category,
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
    overrides: ConfigDep,
    user: OptionalCurrentUserDep = None,
    _: EventStartedDep = None,
) -> Response[PublicChallengeDetail]:
    _check_challenge_visibility(user, overrides)
    structure = await get_detail_structure(session, redis, challenge_id)
    questions = structure.questions

    solved = await _solved_ids(session, user, [q.id for q in questions])
    blocked = await _blocked_ids(session, user, [q.id for q in questions if q.has_trap])
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
            is_blocked=q.id in blocked,
            unlocked_hint_ids=unlocked,
        )
        for i, q in enumerate(questions)
    ]

    challenge_completed = len(questions) > 0 and len(solved | blocked) == len(questions)
    writeup = (
        structure.writeup
        if _writeup_visible(
            challenge_completed=challenge_completed, overrides=overrides
        )
        else None
    )

    # The toggle itself is global, so it ships on /info; reading it here only
    # skips the query when the feature is off.
    my_feedback = (
        await _my_feedback(session, user, structure.id)
        if challenge_completed and user is not None and _feedback_enabled(overrides)
        else None
    )

    return Response(
        data=PublicChallengeDetail(
            id=structure.id,
            title=structure.title,
            description=structure.description,
            writeup=writeup,
            category=structure.category,
            question_count=len(questions),
            solved_count=len(solved),
            challenge_type=structure.challenge_type,
            sequential=structure.sequential,
            questions=question_reads,
            completed=challenge_completed,
            tags=list(structure.tags),
            my_feedback=my_feedback,
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
    overrides: ConfigDep,
    user: RequireTeamDep,
    _: EventActiveDep,
) -> Response[SubmitResult]:
    _check_challenge_visibility(user, overrides)
    await check_config_rate_limit(
        redis, overrides, name="submit", key=f"rl:submit:{user.id}"
    )

    challenge = await _get_active_challenge(session, challenge_id)

    question = next((q for q in challenge.questions if q.id == question_id), None)
    if question is None:
        raise NotFoundError(detail="Question not found in this challenge")

    team_id = user.team_id
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:team_key, :question_key)"),
        {
            "team_key": team_id.int & 0x7FFFFFFF if team_id else 0,
            "question_key": question_id.int & 0x7FFFFFFF,
        },
    )

    solved = await _solved_ids(session, user, [question_id])
    if question_id in solved:
        return Response(
            data=SubmitResult(
                is_correct=True,
                already_solved=True,
                points_earned=0,
            )
        )

    await _check_question_access(session, user, challenge, question)

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
    is_trap = question.is_trap(answer)
    is_correct = False
    timed_out: list[SolutionTimeoutError] = []
    if not is_trap:
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

    await dispatch_hook(session, challenge.on_submit(user, question, answer))

    session.add(
        Submission(
            answer=obj.answer,
            is_correct=is_correct,
            is_trap=is_trap,
            points_earned=points_earned,
            wrong_count_before=wrong_count_before,
            team_id=user.team_id,
            question_id=question_id,
        )
    )
    await session.flush()

    challenge_completed = False
    if is_correct:
        await dispatch_hook(session, challenge.on_solve(user, question))
        all_solved = await _solved_ids(
            session, user, [q.id for q in challenge.questions]
        )
        if len(all_solved) == len(challenge.questions):
            challenge_completed = True
            await dispatch_hook(session, challenge.on_complete(user))
    else:
        await dispatch_hook(session, challenge.on_fail(user, question, answer))

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
            event_type="submission.trap" if is_trap else "submission.wrong",
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
            is_blocked=is_trap,
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
    overrides: ConfigDep,
    user: RequireTeamDep,
    _: EventActiveDep,
) -> Response[PublicHintRead]:
    _check_challenge_visibility(user, overrides)
    challenge = await _get_active_challenge(session, challenge_id)

    question = next((q for q in challenge.questions if q.id == question_id), None)
    if question is None:
        raise NotFoundError(detail="Question not found in this challenge")

    hint = next((h for h in question.hints if h.id == hint_id), None)
    if hint is None:
        raise NotFoundError(detail="Hint not found")

    await _check_question_access(session, user, challenge, question)

    # A hint is bought once per team; teammates unlocking concurrently race on
    # uq_hint_unlock, so let the database settle who pays.
    inserted = await session.execute(
        insert(HintUnlock)
        .values(team_id=user.team_id, hint_id=hint_id, cost_paid=hint.cost)
        .on_conflict_do_nothing(constraint="uq_hint_unlock")
        .returning(HintUnlock.id)
    )
    if inserted.scalar_one_or_none() is not None:
        await dispatch_hook(session, challenge.on_hint_unlock(user, hint))
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
        await asyncio.gather(
            invalidate_stats(redis),
            invalidate_team(redis, user.team_id),
            invalidate_scoreboard(redis, user.team_id),
        )

    return Response(
        data=PublicHintRead(
            id=hint.id,
            title=hint.title,
            cost=hint.cost,
            is_unlocked=True,
            content=hint.content,
        )
    )


@challenge_router.post("/{challenge_id}/feedback")
async def submit_feedback(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    challenge_id: UUID,
    obj: FeedbackBody,
    overrides: ConfigDep,
    user: RequireTeamDep,
    _: EventStartedDep = None,
) -> Response[PublicFeedbackRead]:
    """Rate a challenge the caller's team has fully solved; re-posting edits it."""
    _check_challenge_visibility(user, overrides)
    if not _feedback_enabled(overrides):
        raise FeedbackDisabledError()

    challenge = await _get_active_challenge(session, challenge_id)
    question_ids = [q.id for q in challenge.questions]
    finished = await _solved_ids(session, user, question_ids) | await _blocked_ids(
        session, user, [q.id for q in challenge.questions if q.trap_flags]
    )
    if not question_ids or len(finished) < len(question_ids):
        raise ChallengeNotCompletedError()

    # Teammates racing on uq_challenge_feedback settle in the database: the
    # team owns a single row, and the latest write wins.
    await crud.ChallengeFeedbackCrud.upsert(
        session,
        obj=FeedbackUpsert(
            team_id=cast(UUID, user.team_id),  # RequireTeamDep guarantees a team
            challenge_id=challenge_id,
            rating=obj.rating,
            comment=obj.comment,
        ),
        index_elements=["team_id", "challenge_id"],
        set_=FeedbackBody(rating=obj.rating, comment=obj.comment),
    )

    await emit_event(
        session,
        redis,
        event_type="challenge.feedback",
        actor_id=user.id,
        target_type="challenges",
        target_id=challenge_id,
        target_label=challenge.title,
        ip=get_client_ip(request),
        meta={"team_id": str(user.team_id), "rating": obj.rating},
    )

    return Response(data=PublicFeedbackRead(rating=obj.rating, comment=obj.comment))
