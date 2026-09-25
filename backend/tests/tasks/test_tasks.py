"""Tests for the task queue: transactional enqueue and the worker's wrappers."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import pytest
from pgqueuer import Queries
from pgqueuer.db import AsyncpgDriver
from pgqueuer.types import QueueExecutionMode
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.plugins import loader
from nexctf.plugins.declare import CronDef, TaskDef
from nexctf.plugins.registry import task_registry
from nexctf.tasks import enqueue
from nexctf.tasks.queue import DB_SETTINGS, connect
from nexctf.tasks.worker import _log_plugins_at_info, build_pgqueuer


class _Payload(BaseModel):
    value: int


class _Other(BaseModel):
    value: int


@pytest.fixture
def calls() -> list[Any]:
    return []


@pytest.fixture
def register(isolated_plugins: None) -> Any:
    """Register tasks and crons under the ``tests`` owner for one test."""

    def _register(*defs: TaskDef | CronDef) -> None:
        task_registry.check(list(defs), "tests")
        task_registry.add(list(defs), "tests")

    return _register


@pytest.fixture
def record(calls: list[Any], register: Any) -> TaskDef:
    async def handler(payload: _Payload) -> None:
        calls.append(payload.value)

    task = TaskDef("record", handler, _Payload)
    register(task)
    return task


async def _jobs(queries: Queries) -> list[tuple[object, ...]]:
    rows = await queries.driver.fetch(
        "SELECT entrypoint, status::text, attempts"
        f" FROM {DB_SETTINGS.qualified.queue_table} ORDER BY id"
    )
    return [(r["entrypoint"], r["status"], r["attempts"]) for r in rows]


async def _drain(url: str) -> None:
    """Run a worker over the test database until the queue is empty."""
    conn = await connect(url)
    try:
        pgq = build_pgqueuer(AsyncpgDriver(conn))
        await asyncio.wait_for(
            pgq.qm.run(
                mode=QueueExecutionMode.drain,
                dequeue_timeout=timedelta(seconds=0.5),
            ),
            timeout=20,
        )
    finally:
        await conn.close()


async def test_a_job_is_visible_once_its_transaction_commits(
    db_session: AsyncSession, task_queue: Queries, record: TaskDef
) -> None:
    job_id = await enqueue(db_session, record, _Payload(value=1))

    assert job_id is not None
    assert await _jobs(task_queue) == []
    await db_session.commit()
    assert await _jobs(task_queue) == [("tests.record", "queued", 0)]


async def test_a_rolled_back_transaction_drops_its_job(
    db_session: AsyncSession, task_queue: Queries, record: TaskDef
) -> None:
    await enqueue(db_session, record, _Payload(value=1))
    await db_session.rollback()

    assert await _jobs(task_queue) == []


async def test_a_live_duplicate_is_skipped_and_the_transaction_goes_on(
    db_session: AsyncSession, task_queue: Queries, record: TaskDef
) -> None:
    first = await enqueue(db_session, record, _Payload(value=1), dedupe_key="k")
    second = await enqueue(db_session, record, _Payload(value=2), dedupe_key="k")
    await db_session.commit()

    assert first is not None
    assert second is None
    assert len(await _jobs(task_queue)) == 1


async def test_enqueue_rejects_a_payload_of_the_wrong_type(
    db_session: AsyncSession, task_queue: Queries, record: TaskDef
) -> None:
    with pytest.raises(TypeError):
        await enqueue(db_session, record, _Other(value=1))
    with pytest.raises(TypeError):
        await enqueue(db_session, record)


async def test_enqueue_rejects_a_task_no_plugin_registered(
    db_session: AsyncSession, task_queue: Queries
) -> None:
    async def handler(payload: _Payload) -> None: ...

    with pytest.raises(LookupError):
        await enqueue(
            db_session, TaskDef("orphan", handler, _Payload), _Payload(value=1)
        )


async def test_the_worker_runs_a_queued_task_with_its_payload(
    db_session: AsyncSession,
    task_queue: Queries,
    record: TaskDef,
    calls: list[Any],
    worker_db_url: str,
) -> None:
    await enqueue(db_session, record, _Payload(value=42))
    await db_session.commit()

    await _drain(worker_db_url)

    assert calls == [42]
    assert await _jobs(task_queue) == []


async def test_a_failing_task_is_retried_then_succeeds(
    db_session: AsyncSession,
    task_queue: Queries,
    register: Any,
    calls: list[Any],
    worker_db_url: str,
) -> None:
    async def flaky() -> None:
        calls.append("run")
        if len(calls) == 1:
            raise RuntimeError("transient")

    task = TaskDef("flaky", flaky, retries=2, retry_delay=0)
    register(task)
    await enqueue(db_session, task)
    await db_session.commit()

    await _drain(worker_db_url)

    assert calls == ["run", "run"]
    assert await _jobs(task_queue) == []


async def test_a_task_past_its_timeout_fails_and_is_kept(
    db_session: AsyncSession,
    task_queue: Queries,
    register: Any,
    worker_db_url: str,
) -> None:
    async def hangs() -> None:
        await asyncio.sleep(30)

    task = TaskDef("hangs", hangs, timeout=0.2)
    register(task)
    await enqueue(db_session, task)
    await db_session.commit()

    await _drain(worker_db_url)

    assert await _jobs(task_queue) == [("tests.hangs", "failed", 0)]


async def test_the_worker_schedules_every_registered_cron(
    register: Any, task_queue: Queries
) -> None:
    async def tick() -> None: ...

    register(CronDef("tick", "*/5 * * * *", tick))
    pgq = build_pgqueuer(task_queue.driver)

    scheduled = {(k.entrypoint, k.expression) for k in pgq.sm.registry}
    assert ("tests.tick", "*/5 * * * *") in scheduled
    assert ("core.scheduler_sweep", "* * * * *") in scheduled
    assert ("core.purge_task_queue", "0 3 * * *") in scheduled


def test_the_worker_logs_each_loaded_plugin_at_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plugins log under their own package, which the WARNING root would drop."""
    monkeypatch.setattr(loader, "_plugin_packages", {"nexctf_demo": "demo_pkg"})
    plugin_logger = logging.getLogger("demo_pkg.tasks")
    monkeypatch.setattr(logging.getLogger("demo_pkg"), "level", logging.NOTSET)
    monkeypatch.setattr(logging.getLogger(), "level", logging.WARNING)

    _log_plugins_at_info()

    assert plugin_logger.isEnabledFor(logging.INFO)
