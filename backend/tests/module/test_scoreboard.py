"""Unit tests for nexctf.module.scoreboard.compute functions."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Team, User, UserRole
from nexctf.model.question import Question
from nexctf.model.submission import ScoreAdjustment, Submission
from nexctf.module.scoreboard.compute import (
    compute_scoreboard,
    compute_scoreboard_history,
    compute_team_score,
)
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge

_NOW = datetime.now(timezone.utc)


async def _challenge(session: AsyncSession) -> StandardChallenge:
    ch = StandardChallenge(title="Scoreboard Test Challenge")
    session.add(ch)
    await session.flush()
    return ch


async def _question(session, challenge_id, points=100, malus=None):
    q = Question(label="Flag", points=points, malus=malus, challenge_id=challenge_id)
    session.add(q)
    await session.flush()
    return q


async def _team(session, name="TeamA", bracket=None):
    t = Team(name=name, bracket=bracket)
    session.add(t)
    await session.flush()
    return t


async def _submission(
    session,
    team_id,
    question_id,
    *,
    is_correct=True,
    points_earned=100,
    wrong_count_before=0,
    created_at: datetime | None = None,
):
    s = Submission(
        answer="flag{test}",
        is_correct=is_correct,
        points_earned=points_earned,
        wrong_count_before=wrong_count_before,
        team_id=team_id,
        question_id=question_id,
    )
    session.add(s)
    await session.flush()
    if created_at is not None:
        s.created_at = created_at
        await session.flush()
    return s


async def _adjustment(session, team_id, user_id, amount, reason="bonus"):
    adj = ScoreAdjustment(
        amount=amount,
        reason=reason,
        team_id=team_id,
        created_by_id=user_id,
    )
    session.add(adj)
    await session.flush()
    return adj


async def test_compute_scoreboard_empty(db_session):
    result = await compute_scoreboard(db_session)
    assert result.entries == []


async def test_compute_scoreboard_includes_zero_score_teams(db_session):
    await _team(db_session, "ZeroTeam")
    result = await compute_scoreboard(db_session)
    assert len(result.entries) == 1
    assert result.entries[0].total == 0
    assert result.entries[0].rank == 1


async def test_compute_scoreboard_ranking(db_session):
    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id)
    t1 = await _team(db_session, "High")
    t2 = await _team(db_session, "Low")
    await _submission(db_session, t1.id, q.id, points_earned=200)
    await _submission(db_session, t2.id, q.id, points_earned=50)

    result = await compute_scoreboard(db_session)
    assert result.entries[0].team_name == "High"
    assert result.entries[0].rank == 1
    assert result.entries[1].team_name == "Low"
    assert result.entries[1].rank == 2


async def test_compute_scoreboard_tiebreaker_by_solve_time(db_session):
    ch = await _challenge(db_session)
    q1 = await _question(db_session, ch.id)
    q2 = await _question(db_session, ch.id)
    t_early = await _team(db_session, "Early")
    t_late = await _team(db_session, "Late")
    now = datetime.now(timezone.utc)
    await _submission(db_session, t_early.id, q1.id, points_earned=100, created_at=now)
    await _submission(
        db_session,
        t_late.id,
        q2.id,
        points_earned=100,
        created_at=now + timedelta(seconds=10),
    )

    result = await compute_scoreboard(db_session)
    assert result.entries[0].team_name == "Early"
    assert result.entries[1].team_name == "Late"


async def test_compute_scoreboard_adjustment_only_team_last_solve_at_none(db_session):
    u = User(username="admin_adj", hashed_password="x", role=UserRole.admin)
    db_session.add(u)
    await db_session.flush()

    t = await _team(db_session, "AdjTeam")
    await _adjustment(db_session, t.id, u.id, amount=50)

    result = await compute_scoreboard(db_session)
    entry = next(e for e in result.entries if e.team_name == "AdjTeam")
    assert entry.total == 50


async def test_compute_scoreboard_bracket_reranks_and_lists_brackets(db_session):
    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id)
    student_hi = await _team(db_session, "StudentHigh", bracket="student")
    student_lo = await _team(db_session, "StudentLow", bracket="student")
    pro = await _team(db_session, "Pro", bracket="pro")
    await _submission(db_session, student_hi.id, q.id, points_earned=200)
    await _submission(db_session, student_lo.id, q.id, points_earned=50)
    await _submission(db_session, pro.id, q.id, points_earned=300)

    result = await compute_scoreboard(db_session, bracket="student")
    assert sorted(result.brackets) == ["pro", "student"]
    assert [e.team_name for e in result.entries] == ["StudentHigh", "StudentLow"]
    assert [e.rank for e in result.entries] == [1, 2]


async def test_compute_scoreboard_history_bracket_filters_series(db_session):
    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id, points=100)
    student = await _team(db_session, "StudentHist", bracket="student")
    pro = await _team(db_session, "ProHist", bracket="pro")
    await _submission(db_session, student.id, q.id, points_earned=100)
    await _submission(db_session, pro.id, q.id, points_earned=100)

    result = await compute_scoreboard_history(db_session, bracket="student")
    assert [s.team_name for s in result.series] == ["StudentHist"]


async def test_compute_admin_scoreboard_bracket_reranks_and_lists_brackets(db_session):
    from nexctf.module.scoreboard.compute import compute_admin_scoreboard

    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id)
    student = await _team(db_session, "StudentAdmin", bracket="student")
    pro = await _team(db_session, "ProAdmin", bracket="pro")
    await _submission(db_session, student.id, q.id, points_earned=100)
    await _submission(db_session, pro.id, q.id, points_earned=200)

    result = await compute_admin_scoreboard(db_session, bracket="student")
    assert sorted(result.brackets) == ["pro", "student"]
    assert [e.team_name for e in result.entries] == ["StudentAdmin"]
    assert result.entries[0].rank == 1
    assert result.entries[0].team_bracket == "student"


async def test_compute_team_score_not_found(db_session):
    with pytest.raises(ValueError, match="not found"):
        await compute_team_score(db_session, uuid4())


async def test_compute_team_score_empty(db_session):
    t = await _team(db_session)
    result = await compute_team_score(db_session, t.id)
    assert result.total == 0
    assert result.solves == []
    assert result.adjustments == []


async def test_compute_team_score_with_solves(db_session):
    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id, points=150)
    t = await _team(db_session)
    await _submission(db_session, t.id, q.id, points_earned=150)

    result = await compute_team_score(db_session, t.id)
    assert result.total == 150
    assert result.solve_points == 150
    assert len(result.solves) == 1
    assert result.solves[0].points_earned == 150


async def test_compute_team_score_with_adjustment(db_session):
    u = User(username="admin_ts", hashed_password="x", role=UserRole.admin)
    db_session.add(u)
    await db_session.flush()

    t = await _team(db_session)
    await _adjustment(db_session, t.id, u.id, amount=-20, reason="penalty")

    result = await compute_team_score(db_session, t.id)
    assert result.total == -20
    assert result.adjustment_points == -20
    assert len(result.adjustments) == 1


async def test_compute_team_score_combined(db_session):
    u = User(username="admin_comb", hashed_password="x", role=UserRole.admin)
    db_session.add(u)
    await db_session.flush()

    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id, points=100)
    t = await _team(db_session)
    await _submission(db_session, t.id, q.id, points_earned=100)
    await _adjustment(db_session, t.id, u.id, amount=25)

    result = await compute_team_score(db_session, t.id)
    assert result.total == 125
    assert result.solve_points == 100
    assert result.adjustment_points == 25


async def test_compute_scoreboard_history_empty(db_session):
    result = await compute_scoreboard_history(db_session)
    assert result.series == []


async def test_compute_scoreboard_history_excludes_scoreless_teams(db_session):
    await _team(db_session, "Silent")
    result = await compute_scoreboard_history(db_session)
    assert result.series == []


async def test_compute_scoreboard_history_with_data(db_session):
    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id, points=100)
    t = await _team(db_session, "HistTeam")
    await _submission(db_session, t.id, q.id, points_earned=100)

    result = await compute_scoreboard_history(db_session, limit=10)
    assert len(result.series) == 1
    series = result.series[0]
    assert series.team_name == "HistTeam"
    assert series.rank == 1
    assert len(series.events) == 1
    assert series.events[0].cumulative == 100


async def test_compute_scoreboard_history_limit(db_session):
    ch = await _challenge(db_session)
    q = await _question(db_session, ch.id, points=100)
    for i in range(5):
        t = await _team(db_session, f"Team{i}")
        await _submission(db_session, t.id, q.id, points_earned=100 - i * 10)

    result = await compute_scoreboard_history(db_session, limit=3)
    assert len(result.series) == 3
    assert result.series[0].rank == 1


_FREEZE = _NOW - timedelta(hours=1)
_BEFORE_FREEZE = _FREEZE - timedelta(minutes=30)
_AFTER_FREEZE = _FREEZE + timedelta(minutes=30)


async def test_compute_scoreboard_freeze_excludes_post_freeze_submissions(db_session):
    ch = await _challenge(db_session)
    q1 = await _question(db_session, ch.id, points=100)
    q2 = await _question(db_session, ch.id, points=50)
    t = await _team(db_session, "FreezeTeam")
    await _submission(
        db_session, t.id, q1.id, points_earned=100, created_at=_BEFORE_FREEZE
    )
    await _submission(
        db_session, t.id, q2.id, points_earned=50, created_at=_AFTER_FREEZE
    )

    result = await compute_scoreboard(db_session, freeze_time=_FREEZE)
    entry = next(e for e in result.entries if e.team_name == "FreezeTeam")
    assert entry.total == 100


async def test_compute_scoreboard_freeze_admin_sees_full_data(db_session):
    from nexctf.module.scoreboard.compute import compute_admin_scoreboard

    ch = await _challenge(db_session)
    q1 = await _question(db_session, ch.id, points=100)
    q2 = await _question(db_session, ch.id, points=50)
    t = await _team(db_session, "AdminSeeAll")
    await _submission(
        db_session, t.id, q1.id, points_earned=100, created_at=_BEFORE_FREEZE
    )
    await _submission(
        db_session, t.id, q2.id, points_earned=50, created_at=_AFTER_FREEZE
    )

    result = await compute_admin_scoreboard(db_session)
    entry = next(e for e in result.entries if e.team_name == "AdminSeeAll")
    assert entry.total == 150


async def test_compute_scoreboard_freeze_no_freeze_time_shows_all(db_session):
    ch = await _challenge(db_session)
    q1 = await _question(db_session, ch.id, points=100)
    q2 = await _question(db_session, ch.id, points=50)
    t = await _team(db_session, "NoFreeze")
    await _submission(
        db_session, t.id, q1.id, points_earned=100, created_at=_BEFORE_FREEZE
    )
    await _submission(
        db_session, t.id, q2.id, points_earned=50, created_at=_AFTER_FREEZE
    )

    result = await compute_scoreboard(db_session, freeze_time=None)
    entry = next(e for e in result.entries if e.team_name == "NoFreeze")
    assert entry.total == 150


async def test_compute_scoreboard_history_freeze_excludes_post_freeze_events(
    db_session,
):
    ch = await _challenge(db_session)
    q1 = await _question(db_session, ch.id, points=100)
    q2 = await _question(db_session, ch.id, points=50)
    t = await _team(db_session, "HistFreeze")
    await _submission(
        db_session, t.id, q1.id, points_earned=100, created_at=_BEFORE_FREEZE
    )
    await _submission(
        db_session, t.id, q2.id, points_earned=50, created_at=_AFTER_FREEZE
    )

    result = await compute_scoreboard_history(db_session, limit=10, freeze_time=_FREEZE)
    assert len(result.series) == 1
    series = result.series[0]
    assert len(series.events) == 1
    assert series.events[0].cumulative == 100


async def test_compute_team_score_freeze_excludes_post_freeze_solves(db_session):
    ch = await _challenge(db_session)
    q1 = await _question(db_session, ch.id, points=100)
    q2 = await _question(db_session, ch.id, points=50)
    t = await _team(db_session, "TeamScoreFreeze")
    await _submission(
        db_session, t.id, q1.id, points_earned=100, created_at=_BEFORE_FREEZE
    )
    await _submission(
        db_session, t.id, q2.id, points_earned=50, created_at=_AFTER_FREEZE
    )

    result = await compute_team_score(db_session, t.id, freeze_time=_FREEZE)
    assert result.total == 100
    assert len(result.solves) == 1
