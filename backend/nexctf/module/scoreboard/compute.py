from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from nexctf import crud
from nexctf.model import (
    Hint,
    HintUnlock,
    Question,
    ScoreAdjustment,
    Submission,
    Team,
)
from nexctf.model.custom_field import (
    CustomFieldDefinition,
    CustomFieldTarget,
    CustomFieldValue,
)
from nexctf.schema import (
    AdminScoreboard,
    AdminScoreboardEntry,
    PublicAdjustmentDetail,
    PublicScoreboard,
    PublicScoreboardEntry,
    PublicSolveDetail,
    PublicTeamScoreDetail,
    ScoreboardCustomField,
    ScoreboardHistory,
    ScoreEvent,
    TeamScoreSeries,
)

type SubmissionRow = Row[tuple[UUID, UUID, int, datetime]]
type AdjustmentRow = Row[tuple[UUID, int, datetime]]


async def _fetch_all_submissions(
    session: AsyncSession, before: datetime | None = None
) -> Sequence[SubmissionRow]:
    """Fetch all correct submissions ordered by creation time."""
    stmt = (
        select(
            Submission.team_id,
            Submission.question_id,
            Submission.points_earned,
            Submission.created_at,
        )
        .where(Submission.is_correct.is_(True))
        .order_by(Submission.created_at)
    )
    if before is not None:
        stmt = stmt.where(Submission.created_at <= before)
    return (await session.execute(stmt)).all()


async def _fetch_all_adjustments(
    session: AsyncSession, before: datetime | None = None
) -> Sequence[AdjustmentRow]:
    """Fetch all score adjustments ordered by creation time."""
    stmt = select(
        ScoreAdjustment.team_id, ScoreAdjustment.amount, ScoreAdjustment.created_at
    ).order_by(ScoreAdjustment.created_at)
    if before is not None:
        stmt = stmt.where(ScoreAdjustment.created_at <= before)
    return (await session.execute(stmt)).all()


async def _fetch_all_teams(session: AsyncSession) -> list[Team]:
    """Fetch every team without the crud's default eager loads."""
    return list(await crud.TeamCrud.get_multi(session=session, load_options=[]))


async def _fetch_all_hint_unlocks(
    session: AsyncSession,
    before: datetime | None = None,
    team_id: UUID | None = None,
) -> list[tuple[UUID, UUID, int, datetime]]:
    """Fetch (team_id, question_id, cost_paid, created_at) hint-unlock rows."""
    stmt = (
        select(
            HintUnlock.team_id,
            Hint.question_id,
            HintUnlock.cost_paid,
            HintUnlock.created_at,
        )
        .join(Hint, HintUnlock.hint_id == Hint.id)
        .where(HintUnlock.cost_paid > 0)
    )
    if before is not None:
        stmt = stmt.where(HintUnlock.created_at <= before)
    if team_id is not None:
        stmt = stmt.where(HintUnlock.team_id == team_id)
    return list((await session.execute(stmt)).tuples().all())


def _first_solve_times(
    submissions: Sequence[SubmissionRow],
) -> dict[tuple[UUID, UUID], datetime]:
    """Map (team_id, question_id) to the team's first correct-submission time."""
    first: dict[tuple[UUID, UUID], datetime] = {}
    for sub in submissions:
        first.setdefault((sub.team_id, sub.question_id), sub.created_at)
    return first


def _charged_hint_unlocks(
    hint_unlocks: list[tuple[UUID, UUID, int, datetime]],
    first_solve_at: dict[tuple[UUID, UUID], datetime],
) -> list[tuple[UUID, int, datetime]]:
    """Return (team_id, cost, charged_at) for hints whose question the team solved.

    Charged at max(unlock time, solve time).
    """
    return [
        (team_id, cost, max(unlocked_at, first_solve_at[(team_id, question_id)]))
        for team_id, question_id, cost, unlocked_at in hint_unlocks
        if (team_id, question_id) in first_solve_at
    ]


async def _fetch_scoreboard_fields(
    session: AsyncSession,
) -> tuple[list[ScoreboardCustomField], dict[UUID, dict[str, str]]]:
    """Return scoreboard custom-field columns and per-team values keyed by name."""
    defs = await crud.CustomFieldDefinitionCrud.get_multi(
        session=session,
        filters=[
            CustomFieldDefinition.target == CustomFieldTarget.team,
            CustomFieldDefinition.show_in_scoreboard.is_(True),
            CustomFieldDefinition.is_public.is_(True),
        ],
        order_by=CustomFieldDefinition.name,
    )
    if not defs:
        return [], {}

    names = {d.id: d.name for d in defs}
    values = await crud.CustomFieldValueCrud.get_multi(
        session=session,
        filters=[CustomFieldValue.definition_id.in_(names)],
        load_options=[],
    )

    values_by_team: dict[UUID, dict[str, str]] = {}
    for v in values:
        if v.team_id is not None and v.value:
            values_by_team.setdefault(v.team_id, {})[names[v.definition_id]] = v.value

    fields = [ScoreboardCustomField(name=d.name, label=d.label) for d in defs]
    return fields, values_by_team


def _filter_teams_by_bracket(
    all_teams: list[Team], bracket: str | None
) -> tuple[list[Team], list[str]]:
    """Split teams for *bracket* (or all teams) and the set of brackets in play."""
    brackets = sorted({t.bracket for t in all_teams if t.bracket})
    teams = [t for t in all_teams if t.bracket == bracket] if bracket else all_teams
    return teams, brackets


def _build_ranked_entries(
    submissions: Sequence[SubmissionRow],
    adjustments: Sequence[AdjustmentRow],
    hint_unlocks: list[tuple[UUID, UUID, int, datetime]],
    teams: list[Team],
) -> tuple[list[AdminScoreboardEntry], datetime]:
    """Build ranked scoreboard entries from pre-fetched data."""
    now = datetime.now(tz=UTC)

    subs_by_team: dict[UUID, list[SubmissionRow]] = {}
    for sub in submissions:
        subs_by_team.setdefault(sub.team_id, []).append(sub)

    adj_by_team: dict[UUID, list[AdjustmentRow]] = {}
    for adj in adjustments:
        adj_by_team.setdefault(adj.team_id, []).append(adj)

    hint_cost_by_team: dict[UUID, int] = {}
    for team_id, cost, _ in _charged_hint_unlocks(
        hint_unlocks, _first_solve_times(submissions)
    ):
        hint_cost_by_team[team_id] = hint_cost_by_team.get(team_id, 0) + cost

    entries: list[AdminScoreboardEntry] = []
    for team in teams:
        subs = subs_by_team.get(team.id, [])
        adjs = adj_by_team.get(team.id, [])
        solve_points = sum(s.points_earned for s in subs)
        adjustment_points = sum(a.amount for a in adjs)
        hint_points = -hint_cost_by_team.get(team.id, 0)
        entries.append(
            AdminScoreboardEntry(
                rank=0,
                team_id=team.id,
                team_name=team.name,
                team_bracket=team.bracket,
                total=solve_points + adjustment_points + hint_points,
                solve_points=solve_points,
                adjustment_points=adjustment_points,
                hint_points=hint_points,
                solve_count=len(subs),
                last_solve_at=subs[-1].created_at if subs else None,
            )
        )

    entries.sort(
        key=lambda e: (
            -e.total,
            e.last_solve_at or datetime.max.replace(tzinfo=UTC),
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
    hint_unlocks = await _fetch_all_hint_unlocks(
        session, before=freeze_time, team_id=team_id
    )
    first_solve_at: dict[tuple[UUID, UUID], datetime] = {}
    for s in solves:
        first_solve_at.setdefault((team_id, s.question_id), s.solved_at)
    hint_points = -sum(
        cost for _, cost, _ in _charged_hint_unlocks(hint_unlocks, first_solve_at)
    )

    return PublicTeamScoreDetail(
        team_id=team.id,
        team_name=team.name,
        total=solve_points + adjustment_points + hint_points,
        solve_points=solve_points,
        adjustment_points=adjustment_points,
        hint_points=hint_points,
        solves=solves,
        adjustments=adjustments,
        computed_at=datetime.now(tz=UTC),
    )


async def compute_admin_scoreboard(
    session: AsyncSession, bracket: str | None = None
) -> AdminScoreboard:
    """Compute the full ranked scoreboard with detailed breakdown for all teams."""
    submissions = await _fetch_all_submissions(session)
    adjustments = await _fetch_all_adjustments(session)
    hint_unlocks = await _fetch_all_hint_unlocks(session)
    all_teams = await _fetch_all_teams(session)
    teams, brackets = _filter_teams_by_bracket(all_teams, bracket)

    entries, now = _build_ranked_entries(submissions, adjustments, hint_unlocks, teams)
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
    submissions = await _fetch_all_submissions(session, before=freeze_time)
    adjustments = await _fetch_all_adjustments(session, before=freeze_time)
    hint_unlocks = await _fetch_all_hint_unlocks(session, before=freeze_time)
    all_teams = await _fetch_all_teams(session)
    fields, field_values = await _fetch_scoreboard_fields(session)
    teams, brackets = _filter_teams_by_bracket(all_teams, bracket)

    entries, now = _build_ranked_entries(submissions, adjustments, hint_unlocks, teams)
    return PublicScoreboard(
        entries=[
            PublicScoreboardEntry(
                rank=e.rank,
                team_id=e.team_id,
                team_name=e.team_name,
                team_bracket=e.team_bracket,
                total=e.total,
                custom_fields=field_values.get(e.team_id, {}),
            )
            for e in entries
        ],
        computed_at=now,
        brackets=brackets,
        custom_fields=fields,
    )


async def compute_scoreboard_history(
    session: AsyncSession,
    limit: int = 10,
    freeze_time: datetime | None = None,
    bracket: str | None = None,
) -> ScoreboardHistory:
    """Compute score-over-time series for the top-N teams."""
    now = datetime.now(tz=UTC)

    all_submissions = await _fetch_all_submissions(session, before=freeze_time)
    all_adjustments = await _fetch_all_adjustments(session, before=freeze_time)
    all_hint_unlocks = await _fetch_all_hint_unlocks(session, before=freeze_time)
    teams_by_id = {t.id: t for t in await _fetch_all_teams(session)}

    # Derive team totals and last-solve times from already-fetched data
    team_totals: dict[UUID, int] = {}
    team_last_solve: dict[UUID, datetime] = {}
    for sub in all_submissions:
        team_totals[sub.team_id] = team_totals.get(sub.team_id, 0) + sub.points_earned
        team_last_solve[sub.team_id] = sub.created_at
    for adj in all_adjustments:
        team_totals[adj.team_id] = team_totals.get(adj.team_id, 0) + adj.amount

    charged_unlocks = _charged_hint_unlocks(
        all_hint_unlocks, _first_solve_times(all_submissions)
    )
    for hu_team_id, cost, _ in charged_unlocks:
        team_totals[hu_team_id] = team_totals.get(hu_team_id, 0) - cost

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
            team_last_solve.get(tid) or datetime.max.replace(tzinfo=UTC),
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
    for hu_team_id, cost, charged_at in charged_unlocks:
        if hu_team_id in events_by_team:
            events_by_team[hu_team_id].append((charged_at, -cost))

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
    """Return solves and their total for a team."""
    stmt = (
        select(Submission)
        .where(
            Submission.team_id == team_id,
            Submission.is_correct.is_(True),
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
