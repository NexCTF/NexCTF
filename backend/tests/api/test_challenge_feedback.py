"""Tests for the challenge feedback endpoint gating and upsert."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import ChallengeFeedback, Event, Team, User
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from tests.base import NULL_UUID, ListGuardMixin


async def _setup(
    db_session: AsyncSession, user: User, *, questions: int = 1
) -> tuple[StandardChallenge, list[Question]]:
    """Give *user* a team and an active challenge with *questions* questions."""
    team = Team(name=f"fb_team_{user.username}")
    db_session.add(team)
    await db_session.flush()
    user.team_id = team.id

    challenge = StandardChallenge(title="Feedback Test", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    qs = [
        Question(label=f"Q{i}", points=100, index=i, challenge_id=challenge.id)
        for i in range(questions)
    ]
    db_session.add_all(qs)
    await db_session.flush()
    return challenge, qs


async def _solve(db_session: AsyncSession, c: AsyncClient, challenge, question) -> None:
    from nexctf.plugins.builtin.solution.match.model import MatchSolution

    db_session.add(MatchSolution(question_id=question.id, value="flag"))
    await db_session.flush()
    resp = await c.post(
        f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": "flag"}
    )
    assert resp.json()["data"]["is_correct"] is True


class TestFeedback:
    async def test_disabled_setting_refuses_write(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        """A disabled feature must not accept feedback even from a solver."""
        config_overrides["ctf.enable_challenge_feedback"] = "false"
        c, user = user_client
        challenge, qs = await _setup(db_session, user)
        await _solve(db_session, c, challenge, qs[0])

        resp = await c.post(f"/challenges/{challenge.id}/feedback", json={"rating": 5})

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FEEDBACK-403-DISABLED"

    async def test_incomplete_challenge_refused(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Feedback needs every question of the challenge solved."""
        c, user = user_client
        challenge, qs = await _setup(db_session, user, questions=2)
        await _solve(db_session, c, challenge, qs[0])

        resp = await c.post(f"/challenges/{challenge.id}/feedback", json={"rating": 4})

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FEEDBACK-403-INCOMPLETE"

    async def test_rating_out_of_range_refused(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, user = user_client
        challenge, qs = await _setup(db_session, user)
        await _solve(db_session, c, challenge, qs[0])

        resp = await c.post(f"/challenges/{challenge.id}/feedback", json={"rating": 6})

        assert resp.status_code == 422

    async def test_second_post_edits_instead_of_duplicating(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Re-posting overwrites the team's single row and shows on the detail view."""
        c, user = user_client
        challenge, qs = await _setup(db_session, user)
        await _solve(db_session, c, challenge, qs[0])

        url = f"/challenges/{challenge.id}/feedback"
        first = await c.post(url, json={"rating": 2, "comment": "meh"})
        second = await c.post(url, json={"rating": 5, "comment": "great"})
        assert first.status_code == 200
        assert second.status_code == 200

        count = await db_session.scalar(
            select(func.count())
            .select_from(ChallengeFeedback)
            .where(ChallengeFeedback.team_id == user.team_id)
        )
        assert count == 1

        detail = (await c.get(f"/challenges/{challenge.id}")).json()["data"]
        assert detail["my_feedback"] == {"rating": 5, "comment": "great"}

    async def test_emits_event(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """A saved rating shows up in the admin event log."""
        c, user = user_client
        challenge, qs = await _setup(db_session, user)
        await _solve(db_session, c, challenge, qs[0])

        await c.post(f"/challenges/{challenge.id}/feedback", json={"rating": 4})

        event = await db_session.scalar(
            select(Event).where(Event.event_type == "challenge.feedback")
        )
        assert event is not None
        assert event.actor_id == user.id
        assert event.target_id == challenge.id
        assert event.target_label == challenge.title
        assert event.meta["rating"] == 4
        assert event.meta["team_id"] == str(user.team_id)

    async def test_teamless_user_refused(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = user_client
        resp = await c.post(f"/challenges/{NULL_UUID}/feedback", json={"rating": 3})
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-TEAM"


class TestAdminFeedbackList(ListGuardMixin):
    PREFIX = "/admin/feedback"
