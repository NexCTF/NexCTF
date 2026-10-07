"""Deleting a challenge, question or hint: its contents go, its solve history blocks."""

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import (
    ChallengeFeedback,
    File,
    Hint,
    HintUnlock,
    Question,
    Solution,
    Submission,
    Team,
    User,
)
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

from ..base import make_team


async def _challenge(
    db_session: AsyncSession,
) -> tuple[StandardChallenge, Question, Hint]:
    """A challenge with one question carrying a hint, a solution and a file."""
    challenge = StandardChallenge(title="Doomed", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    question = Question(label="Q", points=100, challenge_id=challenge.id)
    file = File(name="f", s3_key="files/doomed", original_filename="f.txt")
    db_session.add_all([question, file])
    await db_session.flush()
    await db_session.refresh(question, ["files"])
    question.files = [file]
    hint = Hint(question_id=question.id, title="h", content="c")
    db_session.add_all([hint, MatchSolution(value="flag", question_id=question.id)])
    await db_session.flush()
    return challenge, question, hint


async def _count(db_session: AsyncSession, model) -> int:
    return await db_session.scalar(select(func.count()).select_from(model)) or 0


async def _submit(db_session: AsyncSession, team: Team, question: Question) -> None:
    db_session.add(Submission(team_id=team.id, question_id=question.id, answer="x"))
    await db_session.flush()


async def _unlock(db_session: AsyncSession, team: Team, hint: Hint) -> None:
    db_session.add(HintUnlock(team_id=team.id, hint_id=hint.id, cost_paid=0))
    await db_session.flush()


class TestDeleteChallenge:
    async def test_takes_its_questions_and_their_contents(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ):
        c, _ = admin_client
        challenge, _, _ = await _challenge(db_session)

        resp = await c.delete(f"/admin/challenge/{challenge.id}")

        assert resp.status_code == 200
        for model in (StandardChallenge, Question, Hint, Solution):
            assert await _count(db_session, model) == 0
        assert await _count(db_session, File) == 1

    async def test_refuses_while_submissions_reference_it(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        challenge, question, _ = await _challenge(db_session)
        await _submit(db_session, await make_team(db_session, "Red"), question)

        resp = await c.delete(f"/admin/challenge/{challenge.id}")

        assert resp.status_code == 409
        assert "1 submission(s)" in resp.json()["description"]
        assert await _count(db_session, Question) == 1

    async def test_refuses_while_a_hint_unlock_references_it(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        challenge, _, hint = await _challenge(db_session)
        await _unlock(db_session, await make_team(db_session, "Red"), hint)

        resp = await c.delete(f"/admin/challenge/{challenge.id}")

        assert resp.status_code == 409
        assert await _count(db_session, Hint) == 1

    async def test_refuses_while_feedback_references_it(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        challenge, _, _ = await _challenge(db_session)
        team = await make_team(db_session, "Red")
        db_session.add(
            ChallengeFeedback(team_id=team.id, challenge_id=challenge.id, rating=5)
        )
        await db_session.flush()

        resp = await c.delete(f"/admin/challenge/{challenge.id}")

        assert resp.status_code == 409

    async def test_unknown_challenge_is_not_found(self, admin_client):
        c, _ = admin_client
        resp = await c.delete("/admin/challenge/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestDeleteQuestion:
    async def test_takes_its_hints_solutions_and_file_links(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        _, question, _ = await _challenge(db_session)

        resp = await c.delete(f"/admin/question/{question.id}")

        assert resp.status_code == 200
        for model in (Question, Hint, Solution):
            assert await _count(db_session, model) == 0
        assert await _count(db_session, StandardChallenge) == 1
        assert await _count(db_session, File) == 1

    async def test_refuses_while_submissions_reference_it(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        _, question, _ = await _challenge(db_session)
        await _submit(db_session, await make_team(db_session, "Red"), question)

        resp = await c.delete(f"/admin/question/{question.id}")

        assert resp.status_code == 409
        assert await _count(db_session, Question) == 1

    async def test_refuses_while_a_hint_unlock_references_it(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        _, question, hint = await _challenge(db_session)
        await _unlock(db_session, await make_team(db_session, "Red"), hint)

        resp = await c.delete(f"/admin/question/{question.id}")

        assert resp.status_code == 409
        assert "unlocked" in resp.json()["description"]


class TestDeleteHint:
    async def test_deletes_a_hint_nobody_unlocked(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        _, _, hint = await _challenge(db_session)

        resp = await c.delete(f"/admin/hint/{hint.id}")

        assert resp.status_code == 200
        assert await _count(db_session, Hint) == 0

    async def test_refuses_while_a_team_unlocked_it(
        self, admin_client, db_session: AsyncSession
    ):
        c, _ = admin_client
        _, _, hint = await _challenge(db_session)
        await _unlock(db_session, await make_team(db_session, "Red"), hint)

        resp = await c.delete(f"/admin/hint/{hint.id}")

        assert resp.status_code == 409
        assert "1 team(s) unlocked this hint" in resp.json()["description"]
