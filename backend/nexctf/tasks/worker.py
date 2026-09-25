"""Task worker: runs every registered task and cron.

Run with:
    python -m pgqueuer run nexctf.tasks.worker:factory
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import partial

from pgqueuer import PgQueuer
from pgqueuer.db import AsyncpgDriver
from pgqueuer.executors import DatabaseRetryEntrypointExecutor
from pgqueuer.models import Job, Schedule
from pgqueuer.ports.driver import Driver
from pgqueuer.types import Channel

# Imported for its side effect: registers the config definitions.
import nexctf.settings as _  # noqa: F401
from nexctf.core.appconfig import sync_to_redis
from nexctf.core.cache import get_client as get_redis_client
from nexctf.core.db import get_db_context
from nexctf.plugins import load_plugin_registries
from nexctf.plugins.declare import CronDef, TaskDef
from nexctf.plugins.loader import get_plugin_packages
from nexctf.plugins.registry import task_registry
from nexctf.tasks.queue import DB_SETTINGS, build_queries, connect

logger = logging.getLogger(__name__)

_MAX_RETRY_DELAY = timedelta(minutes=5)
_LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


@asynccontextmanager
async def _logged(label: str, timeout: float, level: int) -> AsyncIterator[None]:
    """Log a run's start and outcome with its duration, and cap it at ``timeout``."""
    logger.log(level, "%s started", label)
    start = time.monotonic()
    try:
        async with asyncio.timeout(timeout):
            yield
    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.warning("%s failed after %.1fs: %r", label, elapsed, exc)
        raise
    logger.log(level, "%s done in %.1fs", label, time.monotonic() - start)


def _run_task(task: TaskDef) -> Callable[[Job], Awaitable[None]]:
    """Wrap a task's handler: decode its payload, cap its runtime, log it."""
    schema = task.payload_schema

    async def run(job: Job) -> None:
        label = f"task {job.entrypoint} #{job.id}"
        if job.attempts:
            label += f" (retry {job.attempts})"
        async with _logged(label, task.timeout, logging.INFO):
            if schema is None:
                await task.handler()
            else:
                await task.handler(schema.model_validate_json(job.payload or b""))

    return run


def _run_cron(cron: CronDef) -> Callable[[Schedule], Awaitable[None]]:
    """Wrap a cron's handler to cap its runtime and log it."""

    async def run(schedule: Schedule) -> None:
        async with _logged(f"cron {schedule.entrypoint}", cron.timeout, logging.DEBUG):
            await cron.handler()

    return run


def _retry_executor(task: TaskDef) -> partial[DatabaseRetryEntrypointExecutor]:
    """Build the executor factory that retries a failed run with backoff."""
    return partial(
        DatabaseRetryEntrypointExecutor,
        max_attempts=task.retries,
        initial_delay=timedelta(seconds=task.retry_delay),
        max_delay=_MAX_RETRY_DELAY,
    )


def build_pgqueuer(driver: Driver) -> PgQueuer:
    """Return a PgQueuer running every task and cron currently registered."""
    pgq = PgQueuer(
        connection=driver,
        channel=Channel(DB_SETTINGS.channel),
        queries=build_queries(driver),
    )
    tasks, crons = task_registry.tasks(), task_registry.crons()
    for name, task in tasks.items():
        pgq.entrypoint(
            name,
            concurrency_limit=task.concurrency_limit,
            on_failure="hold",
            executor_factory=_retry_executor(task) if task.retries else None,
        )(_run_task(task))
    for name, cron in crons.items():
        pgq.schedule(name, cron.expression, clean_old=True)(_run_cron(cron))
    logger.info("Running %d task(s) and %d cron(s)", len(tasks), len(crons))
    return pgq


def _configure_logging() -> None:
    """Log NexCTF at INFO and other libraries at WARNING, pgqueuer only once."""
    logging.basicConfig(level=logging.WARNING, format=_LOG_FORMAT)
    logging.getLogger("nexctf").setLevel(logging.INFO)
    logging.getLogger("pgqueuer").propagate = False


def _log_plugins_at_info() -> None:
    """Log each loaded plugin's package at INFO too, as NexCTF's own loggers."""
    for package in get_plugin_packages().values():
        logging.getLogger(package).setLevel(logging.INFO)


async def _load_registries() -> None:
    """Register every enabled plugin's tasks and sync config, as the API does."""
    async with get_db_context() as session:
        load_plugin_registries()
        await sync_to_redis(session, get_redis_client())


@asynccontextmanager
async def factory() -> AsyncIterator[PgQueuer]:
    """Yield the worker's PgQueuer; the ``pgqueuer run`` CLI entry point."""
    _configure_logging()
    await _load_registries()
    _log_plugins_at_info()
    conn = await connect()
    try:
        yield build_pgqueuer(AsyncpgDriver(conn))
    finally:
        await conn.close()
