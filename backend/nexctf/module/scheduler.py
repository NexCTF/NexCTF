"""Scheduler module: built-in job handlers, the due-job sweep and its runs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cronsim import CronSimError
from redis.asyncio import Redis
from sqlalchemy import (
    String,
    cast,
    column,
    delete,
    exists,
    literal,
    select,
    table,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core import appconfig
from nexctf.core.cache import get_client as get_redis_client
from nexctf.core.db import get_db_context
from nexctf.model.scheduler import SchedulerJob, SchedulerTask
from nexctf.module import backup
from nexctf.module.challenge import invalidate as invalidate_challenges
from nexctf.module.notification import create_and_publish
from nexctf.plugins.declare import CronDef, JobDef, Plugin, TaskDef
from nexctf.plugins.registry import SchedulerEntry, scheduler_registry
from nexctf.schema.backup import BackupDatabaseParams, BackupSource
from nexctf.schema.scheduler import (
    SchedulerRunPayload,
    SendNotificationParams,
    TaskStatus,
    ToggleChallengeParams,
)
from nexctf.tasks import enqueue
from nexctf.tasks.queue import DB_SETTINGS
from nexctf.util.async_utils import call_maybe_async
from nexctf.util.cron import next_fire
from nexctf.util.datetime import event_timezone

logger = logging.getLogger(__name__)

_TASK_HISTORY = 100
_RUN_DEDUPE_PREFIX = "scheduler:"
_SWEEP_WINDOW = timedelta(minutes=1)
_QUEUE = table(
    DB_SETTINGS.queue_table,
    column("dedupe_key"),
    column("status"),
    schema=DB_SETTINGS.db_schema,
)


async def handle_send_notification(
    job: SchedulerJob, session: AsyncSession, redis: Redis
) -> None:
    from nexctf.schema.notification import AdminNotificationCreate

    params = SendNotificationParams.model_validate(job.params)

    await create_and_publish(
        session,
        redis,
        AdminNotificationCreate(
            title=params.title,
            content=params.content,
            is_broadcast=params.is_broadcast,
            created_by_id=job.created_by_id,
            team_ids=params.team_ids,
        ),
    )


async def handle_toggle_challenge(
    job: SchedulerJob, session: AsyncSession, redis: Redis
) -> None:
    from nexctf.model import Challenge

    params = ToggleChallengeParams.model_validate(job.params)

    challenge = await session.get(Challenge, params.challenge_id)
    if challenge is None:
        raise ValueError(f"challenge {params.challenge_id} not found")
    challenge.is_active = params.make_active
    await session.flush()


async def handle_backup_database(
    job: SchedulerJob, session: AsyncSession, redis: Redis
) -> None:
    """Dump the database to S3, then drop all but the newest ``keep_last`` dumps."""
    params = BackupDatabaseParams.model_validate(job.params)
    await backup.create(BackupSource.AUTO)
    await backup.prune(params.keep_last)


async def _run_handler(
    task: SchedulerTask,
    job: SchedulerJob,
    entry: SchedulerEntry,
    session: AsyncSession,
    redis: Redis,
) -> None:
    """Run a job's handler and record the outcome on ``task``."""
    try:
        await call_maybe_async(entry.handler, job, session, redis)
        task.status = TaskStatus.SUCCESS
    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.error = str(exc)[:500]
        logger.exception("Job %s failed", job.id)
    task.completed_at = datetime.now(UTC)
    await session.flush()


async def force_run_job(
    job: SchedulerJob, session: AsyncSession, redis: Redis
) -> SchedulerTask:
    """Execute a job immediately without modifying its scheduled state."""
    now = datetime.now(UTC)
    task = await _pending_task(session, job, now)

    try:
        entry = scheduler_registry.get(job.job_type)
    except KeyError:
        _fail(task, f"unregistered job type: {job.job_type}", now)
        await session.flush()
        return task

    await _run_handler(task, job, entry, session, redis)
    await _prune_task_history(session, job)

    if entry.invalidate is not None:
        # The request session commits only once the response has been sent.
        await session.commit()
        await entry.invalidate(redis)
    return task


async def _pending_task(
    session: AsyncSession, job: SchedulerJob, now: datetime
) -> SchedulerTask:
    """Record a pending run of ``job``."""
    task = SchedulerTask(job_id=job.id, status=TaskStatus.PENDING, started_at=now)
    session.add(task)
    await session.flush()
    return task


def _fail(task: SchedulerTask, error: str, now: datetime) -> None:
    """Mark a run as failed with ``error``."""
    task.status = TaskStatus.FAILED
    task.completed_at = now
    task.error = error


async def _prune_task_history(session: AsyncSession, job: SchedulerJob) -> None:
    """Keep only the newest _TASK_HISTORY runs recorded for a job."""
    stale = (
        select(SchedulerTask.id)
        .where(SchedulerTask.job_id == job.id)
        .order_by(SchedulerTask.created_at.desc())
        .offset(_TASK_HISTORY)
    )
    await session.execute(delete(SchedulerTask).where(SchedulerTask.id.in_(stale)))


def next_fire_from_now(expr: str, overrides: dict[str, str]) -> datetime:
    """Return a cron expression's next fire time, read in the event timezone."""
    return next_fire(expr, datetime.now(UTC), event_timezone(overrides))


def _reschedule(job: SchedulerJob, tz: str, fired_at: datetime) -> None:
    """Advance a cron job past ``fired_at``, or retire a one-shot job."""
    if not job.cron_expression:
        job.is_active = False
        return
    try:
        job.scheduled_at = next_fire(job.cron_expression, fired_at, tz)
    except CronSimError:
        job.is_active = False
        logger.warning(
            "Job %s: unparsable cron %r, deactivated", job.id, job.cron_expression
        )


def _run_dedupe_key(job_id: UUID) -> str:
    """Return the dedupe key shared by every queued run of one job."""
    return f"{_RUN_DEDUPE_PREFIX}{job_id}"


async def _queue_run(
    session: AsyncSession, job: SchedulerJob, fire_at: datetime, now: datetime
) -> None:
    """Record a pending run of ``job`` and queue it to start at ``fire_at``."""
    task = await _pending_task(session, job, fire_at)
    queued = await enqueue(
        session,
        RUN_JOB_TASK,
        SchedulerRunPayload(task_id=task.id),
        dedupe_key=_run_dedupe_key(job.id),
        delay=fire_at - now,
    )
    if queued is None:
        _fail(task, "skipped: the previous run is still in progress", now)


async def sweep_due_jobs(session: AsyncSession, redis: Redis) -> None:
    """Queue a run of every job due before the next sweep, then reschedule it.

    A job due later in the window is queued with a delay, so it starts on its
    exact second.
    """
    now = datetime.now(UTC)

    result = await session.execute(
        select(SchedulerJob)
        .where(
            SchedulerJob.scheduled_at <= now + _SWEEP_WINDOW,
            SchedulerJob.is_active.is_(True),
        )
        .with_for_update(skip_locked=True)
    )
    due_jobs = result.scalars().all()

    if not due_jobs:
        return

    logger.info("Queueing %d scheduled job(s)", len(due_jobs))

    tz = event_timezone(await appconfig.fetch_overrides(redis))

    for job in due_jobs:
        fire_at = max(job.scheduled_at, now)
        await _queue_run(session, job, fire_at, now)
        job.last_run = fire_at
        _reschedule(job, tz, fire_at)
        await _prune_task_history(session, job)

    await session.commit()


async def fail_lost_runs(session: AsyncSession) -> None:
    """Fail every pending run whose job no longer has a queued or running job."""
    live_run = exists().where(
        _QUEUE.c.dedupe_key
        == literal(_RUN_DEDUPE_PREFIX) + cast(SchedulerTask.job_id, String),
        cast(_QUEUE.c.status, String).in_(("queued", "picked")),
    )
    await session.execute(
        update(SchedulerTask)
        .where(SchedulerTask.status == TaskStatus.PENDING, ~live_run)
        .values(
            status=TaskStatus.FAILED,
            completed_at=datetime.now(UTC),
            error="lost: the run ended without recording a result",
        )
    )
    await session.commit()


async def run_queued_job(session: AsyncSession, redis: Redis, task_id: UUID) -> None:
    """Execute the pending run ``task_id``; a run no longer pending is skipped."""
    task = await session.get(SchedulerTask, task_id, with_for_update=True)
    if task is None or task.status != TaskStatus.PENDING:
        return
    job = await session.get_one(SchedulerJob, task.job_id)

    try:
        entry = scheduler_registry.get(job.job_type)
    except KeyError:
        logger.warning("Job %s: unregistered type '%s'", job.id, job.job_type)
        _fail(task, f"unregistered job type: {job.job_type}", datetime.now(UTC))
        await session.commit()
        return

    task.started_at = datetime.now(UTC)
    await _run_handler(task, job, entry, session, redis)
    await session.commit()

    if entry.invalidate is not None:
        await entry.invalidate(redis)


async def _run_job_task(payload: SchedulerRunPayload) -> None:
    async with get_db_context() as session:
        await run_queued_job(session, get_redis_client(), payload.task_id)


async def _sweep_cron() -> None:
    async with get_db_context() as session:
        await fail_lost_runs(session)
        await sweep_due_jobs(session, get_redis_client())


RUN_JOB_TASK = TaskDef(
    "scheduler_run",
    _run_job_task,
    SchedulerRunPayload,
    timeout=3600.0,
)


plugin = Plugin(
    jobs=[
        JobDef(
            "send_notification",
            handler=handle_send_notification,
            create_schema=SendNotificationParams,
            update_schema=SendNotificationParams,
        ),
        JobDef(
            "backup_database",
            handler=handle_backup_database,
            create_schema=BackupDatabaseParams,
            update_schema=BackupDatabaseParams,
        ),
        JobDef(
            "toggle_challenge",
            handler=handle_toggle_challenge,
            create_schema=ToggleChallengeParams,
            update_schema=ToggleChallengeParams,
            invalidate=invalidate_challenges,
        ),
    ],
    tasks=[RUN_JOB_TASK],
    crons=[CronDef("scheduler_sweep", "* * * * *", _sweep_cron)],
)
