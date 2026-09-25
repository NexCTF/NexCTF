"""Tests for the task queue retention cron."""

from __future__ import annotations

from datetime import timedelta

from pgqueuer import Queries
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.tasks.maintenance import RETENTION, purge_old_jobs
from nexctf.tasks.queue import DB_SETTINGS

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

    jobs = await task_queue.driver.fetch(f"SELECT id FROM {_NAMES.queue_table}")
    assert {r["id"] for r in jobs} == {new_failed, old_queued}
    logs = await task_queue.driver.fetch(
        f"SELECT aggregated FROM {_NAMES.queue_table_log} ORDER BY id"
    )
    assert [r["aggregated"] for r in logs] == [True, False]
