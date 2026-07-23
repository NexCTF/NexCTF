from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from nexctf.model import Question, ScoreAdjustment, Submission, Team
from nexctf.schema import (
    AdminScoreboard,
    AdminScoreboardEntry,
    PublicAdjustmentDetail,
    PublicScoreboard,
    PublicScoreboardEntry,
    PublicSolveDetail,
    PublicTeamScoreDetail,
    ScoreboardHistory,
    ScoreEvent,
    TeamScoreSeries,
)


async def _fetch_all_submissions(
    session: AsyncSession, before: datetime | None = None
) -> list[Submission]:
    """Fetch all correct, scored submissions ordered by creation time."""
    stmt = (
        select(Submission)
        .where(Submission.is_correct.is_(True), Submission.points_earned > 0)
        .order_by(Submission.created_at)
    )
    if before is not None:
        stmt = stmt.where(Submission.created_at <= before)
    return list((await session.execute(stmt)).scalars().all())


async def _fetch_all_adjustments(
    session: AsyncSession, before: datetime | None = None
) -> list[ScoreAdjustment]:
    """Fetch all score adjustments ordered by creation time."""
    stmt = select(ScoreAdjustment).order_by(ScoreAdjustment.created_at)
    if before is not None:
        stmt = stmt.where(ScoreAdjustment.created_at <= before)
    return list((await session.execute(stmt)).scalars().all())


def _filter_teams_by_bracket(
    all_teams: list[Team], bracket: str | None
) -> tuple[list[Team], list[str]]:
    """Split teams for *bracket* (or all teams) and the set of brackets in play."""
    brackets = sorted({t.bracket for t in all_teams if t.bracket})
    teams = [t for t in all_teams if t.bracket == bracket] if bracket else all_teams
    return teams, brackets


def _build_ranked_entries(
    submissions: list[Submission],
    adjustments: list[ScoreAdjustment],
    teams: list[Team],
) -> tuple[list[AdminScoreboardEntry], datetime]:
    """Build ranked scoreboard entries from pre-fetched data."""
    now = datetime.now(tz=timezone.utc)

    subs_by_team: dict[UUID, list[Submission]] = {}
    for sub in submissions:
        if sub.team_id is not None:
            subs_by_team.setdefault(sub.team_id, []).append(sub)

    adj_by_team: dict[UUID, list[ScoreAdjustment]] = {}
    for adj in adjustments:
        adj_by_team.setdefault(adj.team_id, []).append(adj)

    entries: list[AdminScoreboardEntry] = []
    for team in teams:
        subs = subs_by_team.get(team.id, [])
        adjs = adj_by_team.get(team.id, [])
        solve_points = sum(s.points_earned for s in subs)
        adjustment_points = sum(a.amount for a in adjs)
        entries.append(
            AdminScoreboardEntry(
                rank=0,
                team_id=team.id,
                team_name=team.name,
                team_bracket=team.bracket,
                total=solve_points + adjustment_points,
                solve_points=solve_points,
                adjustment_points=adjustment_points,
                solve_count=len(subs),
                last_solve_at=subs[-1].created_at if subs else None,
            )
        )

    entries.sort(
        key=lambda e: (
            -e.total,
            e.last_solve_at or datetime.max.replace(tzinfo=timezone.utc),
        )
    )
    for rank, entry in enumerate(entries, start=1):
        entry.rank = rank

    return entries, now


async def compute_team_score(
    session: AsyncSession, team_id: UUID, freeze_time: datetime | None = None
) -> PublicTeamScoreDetail:
    """Compute the full score breakdown for a single team."""
    team = await session.get(Team, team_id)
    if team is None:
        raise ValueError(f"Team {team_id} not found")

    solves, solve_points = await _fetch_solves(session, team_id, before=freeze_time)
    adjustments, adjustment_points = await _fetch_adjustments(
        session, team_id, before=freeze_time
    )

    return PublicTeamScoreDetail(
        team_id=team.id,
        team_name=team.name,
        total=solve_points + adjustment_points,
        solve_points=solve_points,
        adjustment_points=adjustment_points,
        solves=solves,
        adjustments=adjustments,
        computed_at=datetime.now(tz=timezone.utc),
    )


async def compute_admin_scoreboard(
    session: AsyncSession, bracket: str | None = None
) -> AdminScoreboard:
    """Compute the full ranked scoreboard with detailed breakdown for all teams."""
    submissions, adjustments, teams_r = await asyncio.gather(
        _fetch_all_submissions(session),
        _fetch_all_adjustments(session),
        session.execute(select(Team)),
    )
    teams, brackets = _filter_teams_by_bracket(list(teams_r.scalars().all()), bracket)

    entries, now = _build_ranked_entries(submissions, adjustments, teams)
    return AdminScoreboard(entries=entries, computed_at=now, brackets=brackets)


async def compute_scoreboard(
    session: AsyncSession,
    freeze_time: datetime | None = None,
    bracket: str | None = None,
) -> PublicScoreboard:
    """Compute the public ranked scoreboard, optionally frozen at *freeze_time*.

    If *bracket* is given, only teams in that bracket are ranked (re-ranked
    from 1, not just filtered from the global ranking).
    """
    submissions, adjustments, teams_r = await asyncio.gather(
        _fetch_all_submissions(session, before=freeze_time),
        _fetch_all_adjustments(session, before=freeze_time),
        session.execute(select(Team)),
    )
    teams, brackets = _filter_teams_by_bracket(list(teams_r.scalars().all()), bracket)

    entries, now = _build_ranked_entries(submissions, adjustments, teams)
    return PublicScoreboard(
        entries=[
            PublicScoreboardEntry(
                rank=e.rank,
                team_id=e.team_id,
                team_name=e.team_name,
                team_bracket=e.team_bracket,
                total=e.total,
            )
            for e in entries
        ],
        computed_at=now,
        brackets=brackets,
    )


async def compute_scoreboard_history(
    session: AsyncSession,
    limit: int = 10,
    freeze_time: datetime | None = None,
    bracket: str | None = None,
) -> ScoreboardHistory:
    """Compute score-over-time series for the top-N teams.

    Fetches all submissions and adjustments in two queries, derives team
    rankings from that same data, then builds the history series — avoiding
    the double-fetch that would result from calling compute_scoreboard first.
    """
    now = datetime.now(tz=timezone.utc)

    all_submissions, all_adjustments, teams_r = await asyncio.gather(
        _fetch_all_submissions(session, before=freeze_time),
        _fetch_all_adjustments(session, before=freeze_time),
        session.execute(select(Team)),
    )
    teams_by_id = {t.id: t for t in teams_r.scalars()}

    # Derive team totals and last-solve times from already-fetched data
    team_totals: dict[UUID, int] = {}
    team_last_solve: dict[UUID, datetime] = {}
    for sub in all_submissions:
        if sub.team_id is not None:
            team_totals[sub.team_id] = (
                team_totals.get(sub.team_id, 0) + sub.points_earned
            )
            team_last_solve[sub.team_id] = sub.created_at
    for adj in all_adjustments:
        if adj.team_id is not None:
            team_totals[adj.team_id] = team_totals.get(adj.team_id, 0) + adj.amount

    if bracket is not None:
        team_totals = {
            tid: total
            for tid, total in team_totals.items()
            if teams_by_id[tid].bracket == bracket
        }

    if not team_totals:
        return ScoreboardHistory(series=[], computed_at=now)

    # Sort: highest total first; ties broken by earliest last_solve_at
    sorted_ids = sorted(
        team_totals,
        key=lambda tid: (
            -team_totals[tid],
            team_last_solve.get(tid) or datetime.max.replace(tzinfo=timezone.utc),
        ),
    )
    top_ids = set(sorted_ids[:limit])

    # Build per-team event lists from the already-fetched data
    events_by_team: dict[UUID, list[tuple[datetime, int]]] = {
        tid: [] for tid in top_ids
    }
    for sub in all_submissions:
        if sub.team_id in events_by_team:
            events_by_team[sub.team_id].append((sub.created_at, sub.points_earned))
    for adj in all_adjustments:
        if adj.team_id in events_by_team:
            events_by_team[adj.team_id].append((adj.created_at, adj.amount))

    series: list[TeamScoreSeries] = []
    for rank, team_id in enumerate(sorted_ids[:limit], start=1):
        if team_id not in teams_by_id:
            continue
        team = teams_by_id[team_id]
        raw = sorted(events_by_team[team_id], key=lambda x: x[0])
        cumulative = 0
        score_events: list[ScoreEvent] = []
        for ts, delta in raw:
            cumulative += delta
            score_events.append(ScoreEvent(ts=ts, cumulative=cumulative))
        series.append(
            TeamScoreSeries(
                team_id=team.id,
                team_name=team.name,
                rank=rank,
                events=score_events,
            )
        )

    return ScoreboardHistory(series=series, computed_at=now)


async def _fetch_solves(
    session: AsyncSession, team_id: UUID, before: datetime | None = None
) -> tuple[list[PublicSolveDetail], int]:
    """Return scored solves and their total for a team."""
    stmt = (
        select(Submission)
        .where(
            Submission.team_id == team_id,
            Submission.is_correct.is_(True),
            Submission.points_earned > 0,
        )
        .options(joinedload(Submission.question).joinedload(Question.challenge))
        .order_by(Submission.created_at)
    )
    if before is not None:
        stmt = stmt.where(Submission.created_at <= before)
    rows = list((await session.execute(stmt)).scalars().all())

    details: list[PublicSolveDetail] = []
    total = 0
    for sub in rows:
        question = sub.question
        challenge = question.challenge
        details.append(
            PublicSolveDetail(
                submission_id=sub.id,
                question_id=question.id,
                question_label=question.label,
                challenge_id=challenge.id,
                challenge_title=challenge.title,
                points_earned=sub.points_earned,
                wrong_attempts=sub.wrong_count_before,
                solved_at=sub.created_at,
            )
        )
        total += sub.points_earned

    return details, total


async def _fetch_adjustments(
    session: AsyncSession, team_id: UUID, before: datetime | None = None
) -> tuple[list[PublicAdjustmentDetail], int]:
    """Return score adjustments and their total for a team."""
    stmt = (
        select(ScoreAdjustment)
        .where(ScoreAdjustment.team_id == team_id)
        .options(joinedload(ScoreAdjustment.challenge))
        .order_by(ScoreAdjustment.created_at)
    )
    if before is not None:
        stmt = stmt.where(ScoreAdjustment.created_at <= before)
    rows = list((await session.execute(stmt)).scalars().all())

    details: list[PublicAdjustmentDetail] = []
    total = 0
    for adj in rows:
        details.append(
            PublicAdjustmentDetail(
                id=adj.id,
                amount=adj.amount,
                reason=adj.reason,
                challenge_id=adj.challenge_id,
                challenge_title=adj.challenge.title if adj.challenge else None,
                applied_at=adj.created_at,
            )
        )
        total += adj.amount

    return details, total
