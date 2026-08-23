"""Tests for trap flags: wrong answers that permanently block a question."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.db import db
from nexctf.model import Submission, Team, User
from nexctf.model.question import Hint, Question
from nexctf.module.submission import recalculate_question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution

TRAP = "NexCTF{TRAP_do_not_submit}"
FLAG = "NexCTF{real_flag}"


async def _setup(
    db_session: AsyncSession, user: User, *, traps: list[str] | None = None
) -> tuple[StandardChallenge, Question]:
    """Give *user* a team and a one-question challenge carrying *traps*."""
    team = Team(name=f"trap_team_{user.id.hex[:8]}")
    db_session.add(team)
    await db_session.flush()
    user.team_id = team.id

    challenge = StandardChallenge(title="Trap Test", is_active=True)
    db_session.add(challenge)
    await db_session.flush()

    question = Question(
        label="Q",
        points=100,
        challenge_id=challenge.id,
        trap_flags=traps if traps is not None else [TRAP],
    )
    db_session.add(question)
    await db_session.flush()
    db_session.add(MatchSolution(value=FLAG, question_id=question.id))
    await db_session.flush()
    return challenge, question


@pytest.fixture
def local_recalc(monkeypatch, db_session: AsyncSession):
    """Run recalculate_question on the test session instead of a locked one."""

    @asynccontextmanager
    async def _yield_test_session(*_args, **_kwargs):
        yield db_session

    monkeypatch.setattr(db, "lock_tables", _yield_test_session)


class TestTrapSubmission:
    async def test_trap_blocks_the_question(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """Submitting a trap flag scores nothing and locks the question."""
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": TRAP}
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["is_blocked"] is True
        assert data["points_earned"] == 0

        sub = await db_session.scalar(
            select(Submission).where(Submission.question_id == question.id)
        )
        assert sub is not None
        assert sub.is_trap is True
        assert sub.is_correct is False

    async def test_trap_match_is_case_insensitive(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        challenge, question = await _setup(db_session, user)

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": TRAP.upper()},
        )

        assert resp.json()["data"]["is_blocked"] is True

    async def test_blocked_team_cannot_submit_the_real_flag(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """Once blocked, even the correct answer is refused."""
        c, user = user_client
        challenge, question = await _setup(db_session, user)
        url = f"/challenges/{challenge.id}/{question.id}/submit"

        await c.post(url, json={"answer": TRAP})
        resp = await c.post(url, json={"answer": FLAG})

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-BLOCKED"

    async def test_blocked_team_cannot_unlock_hints(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """A blocked question can never score, so its hints stop being for sale."""
        c, user = user_client
        challenge, question = await _setup(db_session, user)
        hint = Hint(title="H", content="secret", cost=30, question_id=question.id)
        db_session.add(hint)
        await db_session.flush()

        await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": TRAP}
        )
        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/hints/{hint.id}/unlock"
        )

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-BLOCKED"

    async def test_trap_wins_over_a_matching_solution(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """A value listed as both trap and solution blocks rather than scores."""
        c, user = user_client
        challenge, question = await _setup(db_session, user, traps=[FLAG])

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": FLAG}
        )

        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["points_earned"] == 0


class TestTrapSurvivesRecalculation:
    async def test_recalculation_keeps_the_trap_unscored(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        mock_redis,
        local_recalc,
    ) -> None:
        """recalculate_question runs on every solution write; it must not pay
        out a trap submission."""
        c, user = user_client
        challenge, question = await _setup(db_session, user)
        await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": TRAP}
        )

        await recalculate_question(db_session, mock_redis, question.id)

        sub = await db_session.scalar(
            select(Submission).where(Submission.question_id == question.id)
        )
        assert sub is not None
        assert sub.is_correct is False
        assert sub.is_trap is True
        assert sub.points_earned == 0

    async def test_dropping_the_trap_unblocks_the_team(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        mock_redis,
        local_recalc,
    ) -> None:
        """Clearing trap_flags and recalculating lets the team play again."""
        c, user = user_client
        challenge, question = await _setup(db_session, user)
        url = f"/challenges/{challenge.id}/{question.id}/submit"
        await c.post(url, json={"answer": TRAP})

        question.trap_flags = []
        await db_session.flush()
        await recalculate_question(db_session, mock_redis, question.id)

        resp = await c.post(url, json={"answer": FLAG})
        assert resp.status_code == 200
        assert resp.json()["data"]["is_correct"] is True


class TestAdminTrapEdit:
    """A question PUT carries trap_flags on every save, so only a real change
    may pay for a recalculation (it locks the submissions table)."""

    async def test_adding_a_trap_retroblocks_a_past_answer(
        self,
        admin_client: tuple[AsyncClient, User],
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        local_recalc,
    ) -> None:
        c, user = user_client
        admin, _ = admin_client
        challenge, question = await _setup(db_session, user, traps=[])
        await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": FLAG}
        )

        resp = await admin.put(
            f"/admin/question/{question.id}",
            json={"id": str(question.id), "trap_flags": [FLAG]},
        )

        assert resp.status_code == 200
        sub = await db_session.scalar(
            select(Submission).where(Submission.question_id == question.id)
        )
        assert sub is not None
        assert sub.is_trap is True
        assert sub.is_correct is False
        assert sub.points_earned == 0

    async def test_editing_another_field_skips_the_recalculation(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        user_client: tuple[AsyncClient, User],
        monkeypatch,
    ) -> None:
        _, user = user_client
        admin, _ = admin_client
        _, question = await _setup(db_session, user)

        calls: list[UUID] = []

        async def _spy(_session, _redis, question_id: UUID) -> set[UUID]:
            calls.append(question_id)
            return set()

        monkeypatch.setattr(
            "nexctf.api.routes.admin.question.recalculate_question", _spy
        )
        resp = await admin.put(
            f"/admin/question/{question.id}",
            json={
                "id": str(question.id),
                "label": "Renamed",
                "trap_flags": [TRAP],
            },
        )

        assert resp.status_code == 200
        assert calls == []


class TestTrapBadge:
    async def test_detail_flags_the_question_without_leaking_values(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """Players learn a question has traps, never what they are."""
        c, user = user_client
        challenge, _ = await _setup(db_session, user)

        resp = await c.get(f"/challenges/{challenge.id}")

        assert resp.status_code == 200
        question = resp.json()["data"]["questions"][0]
        assert question["has_trap"] is True
        assert question["is_blocked"] is False
        assert TRAP not in resp.text


class TestBlockedCompletion:
    async def test_blocked_question_releases_the_writeup_and_feedback(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """A trap is terminal, so it must not withhold the writeup forever."""
        c, user = user_client
        challenge, trapped = await _setup(db_session, user)
        challenge.writeup = "The answer was 42"
        solvable = Question(label="Q2", points=100, index=1, challenge_id=challenge.id)
        db_session.add(solvable)
        await db_session.flush()
        db_session.add(MatchSolution(value=FLAG, question_id=solvable.id))
        await db_session.flush()

        await c.post(
            f"/challenges/{challenge.id}/{trapped.id}/submit", json={"answer": TRAP}
        )
        await c.post(
            f"/challenges/{challenge.id}/{solvable.id}/submit", json={"answer": FLAG}
        )

        detail = await c.get(f"/challenges/{challenge.id}")
        feedback = await c.post(
            f"/challenges/{challenge.id}/feedback", json={"rating": 5}
        )

        assert detail.json()["data"]["writeup"] == "The answer was 42"
        assert feedback.status_code == 200

    async def test_sequential_challenge_stays_locked_behind_the_trap(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """A trap on a non-final sequential question locks the rest for good."""
        c, user = user_client
        challenge, trapped = await _setup(db_session, user)
        challenge.sequential = True
        challenge.writeup = "The answer was 42"
        db_session.add(
            Question(label="Q2", points=100, index=1, challenge_id=challenge.id)
        )
        await db_session.flush()

        await c.post(
            f"/challenges/{challenge.id}/{trapped.id}/submit", json={"answer": TRAP}
        )
        detail = await c.get(f"/challenges/{challenge.id}")

        assert detail.json()["data"]["questions"][1]["is_locked"] is True
        assert detail.json()["data"]["writeup"] is None
