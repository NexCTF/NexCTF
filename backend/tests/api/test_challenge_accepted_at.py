"""Tests that plays are dated when the event check accepted them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api import dep
from nexctf.model import HintUnlock, Submission, User
from nexctf.model.question import Hint
from nexctf.module.scoreboard.compute import compute_scoreboard
from tests.base import make_solvable

FLAG = "flag{accepted}"
ACCEPTED_AT = datetime(2026, 1, 1, 11, 59, 59, tzinfo=UTC)
END = ACCEPTED_AT + timedelta(seconds=1)


@pytest.fixture
def last_second(monkeypatch, config_overrides: dict[str, str]) -> None:
    """Accept plays one second before an end that has since passed."""
    monkeypatch.setattr(dep, "datetime", SimpleNamespace(now=lambda _tz: ACCEPTED_AT))
    config_overrides["ctf.end_time"] = END.isoformat()


async def test_a_last_second_solve_counts(
    user_client: tuple[AsyncClient, User], db_session: AsyncSession, last_second: None
) -> None:
    c, user = user_client
    challenge, question = await make_solvable(db_session, user, FLAG)

    resp = await c.post(
        f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": FLAG}
    )

    assert resp.status_code == 200
    assert await db_session.scalar(select(Submission.created_at)) == ACCEPTED_AT
    board = await compute_scoreboard(db_session, end_time=END)
    assert board.entries[0].total == 100


async def test_a_last_second_unlock_is_dated_when_accepted(
    user_client: tuple[AsyncClient, User], db_session: AsyncSession, last_second: None
) -> None:
    c, user = user_client
    challenge, question = await make_solvable(db_session, user, FLAG)
    hint = Hint(title="H", content="secret", cost=10, question_id=question.id)
    db_session.add(hint)
    await db_session.flush()

    resp = await c.post(
        f"/challenges/{challenge.id}/{question.id}/hints/{hint.id}/unlock"
    )

    assert resp.status_code == 200
    assert await db_session.scalar(select(HintUnlock.created_at)) == ACCEPTED_AT
