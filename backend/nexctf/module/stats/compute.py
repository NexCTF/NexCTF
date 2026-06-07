from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from nexctf.model import Challenge, Hint, HintUnlock, Submission, Team, User
from nexctf.schema.stats import (
    AdminTeamChallengeStats,
    ChallengeStats,
    QuestionStats,
    TeamChallengeStats,
)


async def compute_team_challenge_stats(
    session: AsyncSession, team_id: UUID
) -> list[TeamChallengeStats]:
    """Compute per-challenge progress for a team (public schema, no hint details)."""
    admin_stats = await compute_admin_team_challenge_stats(session, team_id)
    return [
        TeamChallengeStats(
            **s.model_dump(exclude={"hint_unlock_count", "hint_cost_spent"})
        )
        for s in admin_stats
    ]


async def compute_admin_team_challenge_stats(
    session: AsyncSession, team_id: UUID
) -> list[AdminTeamChallengeStats]:
    """Compute per-challenge progress for a team with hint unlock data (admin only)."""
    challenges = (
        (
            await session.execute(
                select(Challenge)
                .options(selectinload(Challenge.questions))
                .order_by(Challenge.title)
            )
        )
        .scalars()
        .all()
    )

    if not challenges:
        return []

    all_question_ids = [q.id for c in challenges for q in c.questions]

    if not all_question_ids:
        return [
            AdminTeamChallengeStats(
                challenge_id=c.id,
                challenge_title=c.title,
                question_count=0,
                solved_question_count=0,
                is_solved=False,
                attempt_count=0,
                points_earned=0,
                first_solve_at=None,
                last_solve_at=None,
            )
            for c in challenges
        ]

    submissions = (
        (
            await session.execute(
                select(Submission)
                .where(
                    Submission.team_id == team_id,
                    Submission.question_id.in_(all_question_ids),
                )
                .order_by(Submission.created_at)
            )
        )
        .scalars()
        .all()
    )

    # Load hints to map hint_id → question_id for this challenge set
    hint_rows = (
        await session.execute(
            select(Hint.id, Hint.question_id).where(
                Hint.question_id.in_(all_question_ids)
            )
        )
    ).all()
    hint_id_to_question_id: dict[UUID, UUID] = {
        row.id: row.question_id for row in hint_rows
    }

    # Build question_id → challenge_id mapping
    question_id_to_challenge_id: dict[UUID, UUID] = {}
    for c in challenges:
        for q in c.questions:
            question_id_to_challenge_id[q.id] = c.id

    # Get all user IDs in this team, then load their hint unlocks
    team_user_ids = (
        (await session.execute(select(User.id).where(User.team_id == team_id)))
        .scalars()
        .all()
    )

    hint_unlock_by_challenge: dict[UUID, int] = {}
    hint_cost_by_challenge: dict[UUID, int] = {}
    if team_user_ids and hint_id_to_question_id:
        hint_unlocks = (
            (
                await session.execute(
                    select(HintUnlock).where(
                        HintUnlock.user_id.in_(team_user_ids),
                        HintUnlock.hint_id.in_(hint_id_to_question_id.keys()),
                    )
                )
            )
            .scalars()
            .all()
        )
        for hu in hint_unlocks:
            qid = hint_id_to_question_id.get(hu.hint_id)
            if qid is None:
                continue
            cid = question_id_to_challenge_id.get(qid)
            if cid is None:
                continue
            hint_unlock_by_challenge[cid] = hint_unlock_by_challenge.get(cid, 0) + 1
            hint_cost_by_challenge[cid] = (
                hint_cost_by_challenge.get(cid, 0) + hu.cost_paid
            )

    subs_by_question: dict[UUID, list[Submission]] = {}
    for sub in submissions:
        subs_by_question.setdefault(sub.question_id, []).append(sub)

    result: list[AdminTeamChallengeStats] = []
    for challenge in challenges:
        q_ids = {q.id for q in challenge.questions}
        q_count = len(q_ids)

        c_subs = [s for qid in q_ids for s in subs_by_question.get(qid, [])]
        correct_subs = [s for s in c_subs if s.is_correct]

        solved_q_ids = {s.question_id for s in correct_subs}
        solved_q_count = len(solved_q_ids & q_ids)
        is_solved = q_count > 0 and solved_q_count == q_count
        points_earned = sum(s.points_earned for s in correct_subs)

        first_solve_at = min((s.created_at for s in correct_subs), default=None)
        last_solve_at = max((s.created_at for s in correct_subs), default=None)

        result.append(
            AdminTeamChallengeStats(
                challenge_id=challenge.id,
                challenge_title=challenge.title,
                question_count=q_count,
                solved_question_count=solved_q_count,
                is_solved=is_solved,
                attempt_count=len(c_subs),
                points_earned=points_earned,
                hint_unlock_count=hint_unlock_by_challenge.get(challenge.id, 0),
                hint_cost_spent=hint_cost_by_challenge.get(challenge.id, 0),
                first_solve_at=first_solve_at,
                last_solve_at=last_solve_at,
            )
        )

    return result


async def compute_all_challenge_stats(session: AsyncSession) -> list[ChallengeStats]:
    """Compute stats for every challenge in a single pass over submissions."""
    challenges = (
        (
            await session.execute(
                select(Challenge)
                .options(selectinload(Challenge.questions))
                .order_by(Challenge.title)
            )
        )
        .scalars()
        .all()
    )

    if not challenges:
        return []

    # Build lookup: question_id -> challenge
    q_to_challenge: dict[UUID, Challenge] = {}
    for c in challenges:
        for q in c.questions:
            q_to_challenge[q.id] = c

    all_question_ids = list(q_to_challenge.keys())
    if not all_question_ids:
        return [
            ChallengeStats(
                challenge_id=c.id,
                challenge_title=c.title,
                question_count=0,
                attempt_count=0,
                correct_count=0,
                teams_attempted=0,
                teams_solved=0,
                hint_unlock_count=0,
                hint_cost_spent=0,
                first_blood_team_id=None,
                first_blood_team_name=None,
                first_blood_at=None,
            )
            for c in challenges
        ]

    # Single bulk query — load all relevant submissions with team eager-loaded
    submissions = (
        (
            await session.execute(
                select(Submission)
                .where(Submission.question_id.in_(all_question_ids))
                .options(joinedload(Submission.team))
                .order_by(Submission.created_at)
            )
        )
        .scalars()
        .all()
    )

    # Load all hints to map hint_id → question_id
    hint_rows = (
        await session.execute(
            select(Hint.id, Hint.question_id).where(
                Hint.question_id.in_(all_question_ids)
            )
        )
    ).all()
    hint_id_to_question_id: dict[UUID, UUID] = {
        row.id: row.question_id for row in hint_rows
    }

    # Load all hint unlocks (bulk, then map via hint)
    hint_unlocks = []
    if hint_id_to_question_id:
        hint_unlocks = (
            (
                await session.execute(
                    select(HintUnlock).where(
                        HintUnlock.hint_id.in_(hint_id_to_question_id.keys())
                    )
                )
            )
            .scalars()
            .all()
        )

    # Accumulate per-challenge and per-question counters in a single pass
    attempt_by_c: dict[UUID, int] = {}
    correct_by_c: dict[UUID, int] = {}
    teams_attempted_by_c: dict[UUID, set[UUID]] = {}
    attempt_by_q: dict[UUID, int] = {}
    correct_by_q: dict[UUID, int] = {}
    teams_attempted_by_q: dict[UUID, set[UUID]] = {}
    # first_correct[challenge_id][team_id][question_id] = earliest correct datetime
    first_correct: dict[UUID, dict[UUID, dict[UUID, datetime]]] = {}
    # first_correct_by_q[question_id][team_id] = earliest correct datetime
    first_correct_by_q: dict[UUID, dict[UUID, datetime]] = {}
    # keep a team object reference for name resolution
    team_objs: dict[UUID, Team] = {}

    for sub in submissions:
        c = q_to_challenge.get(sub.question_id)
        if c is None:
            continue
        cid = c.id
        qid = sub.question_id

        attempt_by_c[cid] = attempt_by_c.get(cid, 0) + 1
        attempt_by_q[qid] = attempt_by_q.get(qid, 0) + 1

        if sub.team_id is not None:
            teams_attempted_by_c.setdefault(cid, set()).add(sub.team_id)
            teams_attempted_by_q.setdefault(qid, set()).add(sub.team_id)
            if sub.team is not None:
                team_objs[sub.team_id] = sub.team

        if sub.is_correct:
            correct_by_c[cid] = correct_by_c.get(cid, 0) + 1
            correct_by_q[qid] = correct_by_q.get(qid, 0) + 1
            if sub.team_id is not None:
                c_map = first_correct.setdefault(cid, {})
                t_map = c_map.setdefault(sub.team_id, {})
                if qid not in t_map:
                    t_map[qid] = sub.created_at
                q_map = first_correct_by_q.setdefault(qid, {})
                if sub.team_id not in q_map:
                    q_map[sub.team_id] = sub.created_at

    # Accumulate hint unlock counts per question and per challenge
    hint_unlock_by_q: dict[UUID, int] = {}
    hint_cost_by_q: dict[UUID, int] = {}
    hint_unlock_by_c: dict[UUID, int] = {}
    hint_cost_by_c: dict[UUID, int] = {}

    for hu in hint_unlocks:
        qid = hint_id_to_question_id.get(hu.hint_id)
        if qid is None:
            continue
        c = q_to_challenge.get(qid)
        if c is None:
            continue
        cid = c.id
        hint_unlock_by_q[qid] = hint_unlock_by_q.get(qid, 0) + 1
        hint_cost_by_q[qid] = hint_cost_by_q.get(qid, 0) + hu.cost_paid
        hint_unlock_by_c[cid] = hint_unlock_by_c.get(cid, 0) + 1
        hint_cost_by_c[cid] = hint_cost_by_c.get(cid, 0) + hu.cost_paid

    result: list[ChallengeStats] = []
    for c in challenges:
        cid = c.id
        q_ids = {q.id for q in c.questions}
        q_count = len(q_ids)

        first_blood_team_id: UUID | None = None
        first_blood_team_name: str | None = None
        first_blood_at: datetime | None = None
        teams_solved_count = 0

        if q_count > 0:
            solved_team_ids: list[UUID] = []
            completion_time_by_team: dict[UUID, datetime] = {}
            for team_id, q_map in first_correct.get(cid, {}).items():
                if set(q_map.keys()) >= q_ids:
                    teams_solved_count += 1
                    solved_team_ids.append(team_id)
                    completion_time_by_team[team_id] = max(q_map.values())

            if solved_team_ids:
                first_blood_team_id = min(
                    solved_team_ids, key=lambda tid: completion_time_by_team[tid]
                )
                first_blood_at = completion_time_by_team[first_blood_team_id]
                t = team_objs.get(first_blood_team_id)
                first_blood_team_name = t.name if t else None

        # Build per-question stats (sorted by question index)
        question_stats: list[QuestionStats] = []
        for q in sorted(c.questions, key=lambda x: x.index):
            qid = q.id
            q_first_blood_name: str | None = None
            q_first_blood_at: datetime | None = None
            q_fb_map = first_correct_by_q.get(qid, {})
            if q_fb_map:
                q_fb_team_id = min(q_fb_map, key=lambda tid: q_fb_map[tid])
                q_first_blood_at = q_fb_map[q_fb_team_id]
                t = team_objs.get(q_fb_team_id)
                q_first_blood_name = t.name if t else None

            question_stats.append(
                QuestionStats(
                    question_id=qid,
                    question_label=q.label,
                    question_index=q.index,
                    attempt_count=attempt_by_q.get(qid, 0),
                    correct_count=correct_by_q.get(qid, 0),
                    teams_attempted=len(teams_attempted_by_q.get(qid, set())),
                    teams_solved=len(first_correct_by_q.get(qid, {})),
                    hint_unlock_count=hint_unlock_by_q.get(qid, 0),
                    hint_cost_spent=hint_cost_by_q.get(qid, 0),
                    first_blood_team_name=q_first_blood_name,
                    first_blood_at=q_first_blood_at,
                )
            )

        result.append(
            ChallengeStats(
                challenge_id=cid,
                challenge_title=c.title,
                question_count=q_count,
                attempt_count=attempt_by_c.get(cid, 0),
                correct_count=correct_by_c.get(cid, 0),
                teams_attempted=len(teams_attempted_by_c.get(cid, set())),
                teams_solved=teams_solved_count,
                hint_unlock_count=hint_unlock_by_c.get(cid, 0),
                hint_cost_spent=hint_cost_by_c.get(cid, 0),
                first_blood_team_id=first_blood_team_id,
                first_blood_team_name=first_blood_team_name,
                first_blood_at=first_blood_at,
                questions=question_stats,
            )
        )

    return result
