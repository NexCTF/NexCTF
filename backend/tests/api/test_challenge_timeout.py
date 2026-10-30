"""Tests for an answer whose check times out: retryable, never a wrong answer."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.exceptions import SolutionTimeoutError
from nexctf.model import Submission, User
from nexctf.model.event import Event
from nexctf.plugins.builtin.solution.match.model import MatchSolution
from nexctf.plugins.builtin.solution.regex.model import RegexSolution
from tests.base import make_solvable

FLAG = "flag{slow}"


@pytest.fixture
def slow_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every exact-match check time out."""

    async def _slow(self: MatchSolution, *_a: object, **_kw: object) -> bool:
        raise SolutionTimeoutError(self.id, self.value)

    monkeypatch.setattr(MatchSolution, "verify", _slow)


async def _count(db_session: AsyncSession, *where: ColumnElement[bool]) -> int:
    return (
        await db_session.scalar(
            select(func.count()).select_from(Submission).where(*where)
        )
        or 0
    )


async def test_a_timed_out_check_is_retryable_and_not_recorded(
    user_client: tuple[AsyncClient, User], db_session: AsyncSession, slow_match: None
) -> None:
    c, user = user_client
    challenge, question = await make_solvable(db_session, user, FLAG)

    resp = await c.post(
        f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": FLAG}
    )

    assert resp.status_code == 503
    assert resp.json()["error_code"] == "SUB-503-TIMEOUT"
    assert await _count(db_session) == 0
    events = await db_session.scalars(
        select(Event.event_type).where(Event.target_id == challenge.id)
    )
    assert list(events) == ["solution.timeout"]


async def test_a_timed_out_check_adds_no_malus(
    user_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c, user = user_client
    challenge, question = await make_solvable(db_session, user, FLAG)
    question.malus = 30
    await db_session.flush()
    url = f"/challenges/{challenge.id}/{question.id}/submit"
    real_verify = MatchSolution.verify

    async def _slow(self: MatchSolution, *_a: object, **_kw: object) -> bool:
        raise SolutionTimeoutError(self.id, self.value)

    monkeypatch.setattr(MatchSolution, "verify", _slow)
    assert (await c.post(url, json={"answer": FLAG})).status_code == 503
    monkeypatch.setattr(MatchSolution, "verify", real_verify)

    resp = await c.post(url, json={"answer": FLAG})

    assert resp.json()["data"]["points_earned"] == 100
    assert await _count(db_session, Submission.is_correct.is_(False)) == 0


async def test_another_matching_solution_still_solves(
    user_client: tuple[AsyncClient, User], db_session: AsyncSession, slow_match: None
) -> None:
    c, user = user_client
    challenge, question = await make_solvable(db_session, user, FLAG)
    db_session.add(RegexSolution(pattern=r"flag\{.*\}", question_id=question.id))
    await db_session.flush()

    resp = await c.post(
        f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": FLAG}
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["is_correct"] is True
