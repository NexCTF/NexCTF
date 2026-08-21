"""Unit tests for nexctf.module.stats.compute team challenge stats."""

from uuid import uuid4

from nexctf.model import Hint, HintUnlock, Question, Submission, Team
from nexctf.module.scoreboard.compute import compute_team_score
from nexctf.module.stats.compute import (
    compute_admin_team_challenge_stats,
    compute_all_challenge_stats,
    compute_team_challenge_stats,
)
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge


async def test_question_net_points_deduct_hints_only_when_solved(db_session):
    ch = StandardChallenge(title="Stats Net Points Test")
    db_session.add(ch)
    await db_session.flush()
    q_solved = Question(label="Q1", points=100, challenge_id=ch.id)
    q_unsolved = Question(label="Q2", points=50, challenge_id=ch.id)
    db_session.add_all([q_solved, q_unsolved])
    await db_session.flush()

    team = Team(name=f"stats_{uuid4().hex[:8]}")
    db_session.add(team)
    await db_session.flush()

    h1 = Hint(title="H1", content="c", cost=25, question_id=q_solved.id)
    h2 = Hint(title="H2", content="c", cost=10, question_id=q_unsolved.id)
    db_session.add_all([h1, h2])
    await db_session.flush()
    db_session.add_all(
        [
            HintUnlock(team_id=team.id, hint_id=h1.id, cost_paid=25),
            HintUnlock(team_id=team.id, hint_id=h2.id, cost_paid=10),
            Submission(
                answer="a",
                is_correct=True,
                points_earned=100,
                team_id=team.id,
                question_id=q_solved.id,
            ),
        ]
    )
    await db_session.flush()

    stats = await compute_team_challenge_stats(db_session, team.id)
    c = next(s for s in stats if s.challenge_id == ch.id)
    by_label = {q.question_label: q for q in c.questions}
    assert by_label["Q1"].points_earned == 75
    assert by_label["Q2"].points_earned == 0
    assert c.points_earned == 75

    admin = await compute_admin_team_challenge_stats(db_session, team.id)
    assert next(s for s in admin if s.challenge_id == ch.id).points_earned == 75

    # Pin the stats netting rule to the scoreboard's charging rule.
    detail = await compute_team_score(db_session, team.id)
    assert sum(q.points_earned for q in c.questions) == detail.total


async def test_admin_stats_carry_hint_unlocks_public_does_not(db_session):
    ch = StandardChallenge(title="Stats Hint Detail Test")
    db_session.add(ch)
    await db_session.flush()
    q = Question(label="Q1", points=100, challenge_id=ch.id)
    q_solved = Question(label="Q2", points=50, challenge_id=ch.id)
    db_session.add_all([q, q_solved])
    await db_session.flush()

    team = Team(name=f"stats_{uuid4().hex[:8]}")
    db_session.add(team)
    await db_session.flush()

    h1 = Hint(title="H1", content="secret", cost=25, question_id=q.id)
    h2 = Hint(title="H2", content="secret", cost=10, question_id=q.id)
    db_session.add_all([h1, h2])
    await db_session.flush()
    db_session.add_all(
        [
            HintUnlock(team_id=team.id, hint_id=h1.id, cost_paid=25),
            HintUnlock(team_id=team.id, hint_id=h2.id, cost_paid=10),
            Submission(
                answer="a",
                is_correct=True,
                points_earned=50,
                team_id=team.id,
                question_id=q_solved.id,
            ),
        ]
    )
    await db_session.flush()

    admin_stats = await compute_admin_team_challenge_stats(db_session, team.id)
    c = next(s for s in admin_stats if s.challenge_id == ch.id)
    by_label = {q.question_label: q for q in c.questions}
    assert by_label["Q1"].solved_at is None
    assert by_label["Q2"].solved_at is not None
    unlocked = by_label["Q1"].hints
    assert [u.title for u in unlocked] == ["H1", "H2"]
    assert sum(u.cost_paid for u in unlocked) == 35
    assert unlocked[0].unlocked_at is not None
    assert not hasattr(unlocked[0], "content")

    # Hint titles and unlock timings must not reach the public team profile.
    public_stats = await compute_team_challenge_stats(db_session, team.id)
    pc = next(s for s in public_stats if s.challenge_id == ch.id)
    pq = next(q for q in pc.questions if q.question_label == "Q1")
    assert pq.hint_unlock_count == 2
    assert not hasattr(pq, "hints")
    assert not hasattr(pq, "solved_at")


async def test_challenge_stats_carry_category_and_points(db_session):
    ch = StandardChallenge(title="Stats Category Test", category="pwn")
    db_session.add(ch)
    await db_session.flush()
    db_session.add_all(
        [
            Question(label="Q1", points=100, challenge_id=ch.id),
            Question(label="Q2", points=50, challenge_id=ch.id),
        ]
    )
    await db_session.flush()

    stats = await compute_all_challenge_stats(db_session)
    c = next(s for s in stats if s.challenge_id == ch.id)
    assert c.category == "pwn"
    assert c.points == 150
    assert sorted(q.points for q in c.questions) == [50, 100]
