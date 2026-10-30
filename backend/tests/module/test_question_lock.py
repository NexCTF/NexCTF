"""Tests for the per-question lock shared by submits and recalculations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from fastapi_toolsets.exceptions import LockTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nexctf.module.submission import lock_question


@pytest.fixture
async def sessions(worker_db_url: str) -> AsyncIterator[async_sessionmaker]:
    engine = create_async_engine(worker_db_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def _holding(
    maker: async_sessionmaker,
    question_id: UUID,
    *,
    shared: bool = False,
    timeout: str | None = None,
) -> AsyncSession:
    """Open a transaction holding the lock on *question_id*."""
    session = maker()
    await session.begin()
    await lock_question(session, question_id, shared=shared, timeout=timeout)
    return session


async def test_submits_share_the_lock(sessions: async_sessionmaker) -> None:
    question_id = uuid4()
    first = await _holding(sessions, question_id, shared=True)
    try:
        second = await _holding(sessions, question_id, shared=True, timeout="200ms")
        await second.rollback()
    finally:
        await first.rollback()


async def test_recalculation_waits_for_a_submit(sessions: async_sessionmaker) -> None:
    question_id = uuid4()
    submit = await _holding(sessions, question_id, shared=True)
    try:
        with pytest.raises(LockTimeoutError):
            await _holding(sessions, question_id, timeout="200ms")
    finally:
        await submit.rollback()


async def test_submit_waits_for_a_recalculation(sessions: async_sessionmaker) -> None:
    question_id = uuid4()
    recalc = await _holding(sessions, question_id)
    try:
        with pytest.raises(LockTimeoutError):
            await _holding(sessions, question_id, shared=True, timeout="200ms")
    finally:
        await recalc.rollback()


async def test_other_questions_stay_free(sessions: async_sessionmaker) -> None:
    recalc = await _holding(sessions, uuid4())
    try:
        other = await _holding(sessions, uuid4(), shared=True, timeout="200ms")
        await other.rollback()
    finally:
        await recalc.rollback()
