"""Tests for the task queue and session retention crons."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pgqueuer import Queries
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.enums import SessionWindow
from nexctf.model import User, UserSession, UserToken
from nexctf.module import session as session_module
from nexctf.module.session import (
    TOKEN_RETENTION,
    purge_expired_access,
    sessions_by_address,
)
from nexctf.tasks.maintenance import RETENTION, plugin, purge_old_jobs
from nexctf.tasks.queue import DB_SETTINGS

from ..base import add_login, add_session, add_sighting, make_user

DAY = timedelta(days=1)
MINUTE = timedelta(minutes=1)

_NAMES = DB_SETTINGS.qualified


async def _age(queries: Queries, job_id: int, status: str, age: timedelta) -> None:
    await queries.driver.execute(
        f"UPDATE {_NAMES.queue_table} SET status = $2::{_NAMES.queue_status_type},"
        " updated = NOW() - $3::interval WHERE id = $1",
        job_id,
        status,
        age,
    )


async def _log(queries: Queries, aggregated: bool, age: timedelta) -> None:
    await queries.driver.execute(
        f"INSERT INTO {_NAMES.queue_table_log}"
        " (job_id, status, priority, entrypoint, aggregated, created)"
        " VALUES (0, 'successful', 0, 'x', $1, NOW() - $2::interval)",
        aggregated,
        age,
    )


async def test_old_failed_jobs_and_aggregated_logs_are_purged(
    db_session: AsyncSession, task_queue: Queries
) -> None:
    old = RETENTION + timedelta(days=1)
    old_failed, new_failed, old_queued = await task_queue.enqueue(
        ["x", "x", "x"], [None, None, None], [0, 0, 0]
    )
    await _age(task_queue, old_failed, "failed", old)
    await _age(task_queue, new_failed, "failed", timedelta(days=1))
    await _age(task_queue, old_queued, "queued", old)
    await task_queue.driver.execute(f"DELETE FROM {_NAMES.queue_table_log}")
    await _log(task_queue, True, old)
    await _log(task_queue, True, timedelta(days=1))
    await _log(task_queue, False, old)

    await purge_old_jobs(db_session)
    await db_session.commit()

    jobs = await task_queue.driver.fetch(f"SELECT id FROM {_NAMES.queue_table}")
    assert {r["id"] for r in jobs} == {new_failed, old_queued}
    logs = await task_queue.driver.fetch(
        f"SELECT aggregated FROM {_NAMES.queue_table_log} ORDER BY id"
    )
    assert [r["aggregated"] for r in logs] == [True, False]


def _token(user: User, name: str, expired_ago: timedelta | None) -> UserToken:
    expires_at = None if expired_ago is None else datetime.now(UTC) - expired_ago
    return UserToken(
        user_id=user.id, name=name, token_hash=uuid4().hex, expires_at=expires_at
    )


class TestPurgeExpiredAccess:
    async def test_drops_sessions_once_expired(self, db_session: AsyncSession):
        user = await make_user(db_session, "purged")
        await add_session(db_session, user, ip="10.0.0.1", expires_in=-MINUTE)
        live = await add_session(db_session, user, ip="10.0.0.1", expires_in=MINUTE)

        await purge_expired_access(db_session)

        assert set(await db_session.scalars(select(UserSession.id))) == {live.id}

    async def test_drops_a_backlog_in_batches(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(session_module, "PURGE_BATCH", 2)
        user = await make_user(db_session, "backlog")
        for _ in range(5):
            await add_session(db_session, user, ip="10.0.0.1", expires_in=-MINUTE)

        await purge_expired_access(db_session)

        assert list(await db_session.scalars(select(UserSession.id))) == []

    async def test_drops_tokens_past_the_retention(self, db_session: AsyncSession):
        user = await make_user(db_session, "scripted")
        db_session.add_all(
            [
                _token(user, "old", TOKEN_RETENTION + DAY),
                _token(user, "recent", DAY),
                _token(user, "forever", None),
            ]
        )
        await db_session.flush()

        await purge_expired_access(db_session)

        names = await db_session.scalars(select(UserToken.name))
        assert set(names) == {"recent", "forever"}

    async def test_sightings_keep_the_purged_token_name(self, db_session: AsyncSession):
        user = await make_user(db_session, "scripted")
        token = _token(user, "solver", TOKEN_RETENTION + DAY)
        db_session.add(token)
        await db_session.flush()
        sighting = await add_sighting(db_session, user, "curl/8.5", token=token)

        await purge_expired_access(db_session)
        await db_session.refresh(sighting)

        assert (sighting.token_id, sighting.token_name) == (None, "solver")

    async def test_login_history_outlives_the_purge(self, db_session: AsyncSession):
        user = await make_user(db_session, "returning")
        ip = "10.0.0.1"
        await add_session(db_session, user, ip=ip, expires_in=-MINUTE)
        await add_login(db_session, user, ip=ip)

        await purge_expired_access(db_session)

        overview = await sessions_by_address(db_session, SessionWindow.ALL, None)
        assert [a.ip for a in overview.addresses] == [ip]


def test_purge_runs_as_a_core_cron() -> None:
    assert "purge_expired_sessions" in {cron.name for cron in plugin.crons}
