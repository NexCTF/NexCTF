"""Unit tests for nexctf.module.stats.compute team challenge stats."""

from uuid import uuid4

from nexctf.model import Hint, HintUnlock, Question, Submission, Team
from nexctf.module.scoreboard.compute import compute_team_score
from nexctf.module.stats.compute import compute_team_challenge_stats
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

    # Pin the stats netting rule to the scoreboard's charging rule.
    detail = await compute_team_score(db_session, team.id)
    assert sum(q.points_earned for q in c.questions) == detail.total
