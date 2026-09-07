"""Tests for the prompt-injection canary planted in challenge text."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Event, Submission, Team, User
from nexctf.model.question import Question
from nexctf.module import canary
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

FLAG = "NexCTF{real_flag}"


async def _setup(
    db_session: AsyncSession, user: User
) -> tuple[StandardChallenge, Question]:
    """Give *user* a team and a one-question challenge with descriptions."""
    team = Team(name=f"canary_team_{user.id.hex[:8]}")
    db_session.add(team)
    await db_session.flush()
    user.team_id = team.id

    challenge = StandardChallenge(
        title="Canary Test", description="Challenge text", is_active=True
    )
    db_session.add(challenge)
    await db_session.flush()

    question = Question(
        label="Q", description="Question text", points=100, challenge_id=challenge.id
    )
    db_session.add(question)
    await db_session.flush()
    db_session.add(MatchSolution(value=FLAG, question_id=question.id))
    await db_session.flush()
    return challenge, question


class TestCanaryToken:
    def test_token_is_challenge_specific(self) -> None:
        a, b = uuid4(), uuid4()
        assert canary.matches(a, canary.token(a))
        assert not canary.matches(b, canary.token(a))

    def test_match_ignores_case_and_padding(self) -> None:
        cid = uuid4()
        assert canary.matches(cid, f"  {canary.token(cid).upper()}  ")

    def test_token_does_not_look_like_a_flag(self) -> None:
        assert "{" not in canary.token(uuid4())


class TestCanaryDisabled:
    async def test_description_is_untouched(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, _ = await _setup(db_session, user)

        data = (await c.get(f"/challenges/{challenge.id}")).json()["data"]

        assert data["description"] == "Challenge text"
        assert data["questions"][0]["description"] == "Question text"

    async def test_token_is_just_a_wrong_answer(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": canary.token(challenge.id)},
        )

        assert resp.json()["data"]["is_correct"] is False
        event = await db_session.scalar(
            select(Event).where(Event.event_type == "submission.canary")
        )
        assert event is None


class TestCanaryEnabled:
    @pytest.fixture
    def config_overrides(self) -> dict[str, str]:
        return {canary.CONFIG_KEY: "true"}

    async def test_token_is_planted_in_player_text(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, _ = await _setup(db_session, user)
        token = canary.token(challenge.id)

        data = (await c.get(f"/challenges/{challenge.id}")).json()["data"]

        assert token in data["description"]
        assert token in data["questions"][0]["description"]
        assert data["description"].startswith("Challenge text")

    async def test_submitting_it_is_recorded_without_punishment(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """The player just sees a wrong answer; the admin gets an event."""
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": canary.token(challenge.id)},
        )

        assert resp.json()["data"]["is_correct"] is False

        sub = await db_session.scalar(
            select(Submission).where(Submission.question_id == question.id)
        )
        assert sub is not None
        assert sub.is_trap is False
        assert sub.points_earned == 0

        event = await db_session.scalar(
            select(Event).where(Event.event_type == "submission.canary")
        )
        assert event is not None
        assert event.actor_id == user.id
        assert event.target_id == challenge.id

    async def test_another_challenges_token_is_a_plain_wrong_answer(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": canary.token(uuid4())},
        )

        event = await db_session.scalar(
            select(Event).where(Event.event_type == "submission.canary")
        )
        assert event is None

    async def test_the_real_flag_still_scores(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": FLAG},
        )

        assert resp.json()["data"]["is_correct"] is True
