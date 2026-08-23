"""Scheduler module: built-in handlers + worker tick function."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from cronsim import CronSimError
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core import appconfig
from nexctf.model.scheduler import SchedulerJob, SchedulerTask
from nexctf.module.challenge import invalidate as invalidate_challenges
from nexctf.module.notification import create_and_publish
from nexctf.plugins.registry import SchedulerEntry, scheduler_registry
from nexctf.schema.scheduler import (
    SendNotificationParams,
    TaskStatus,
    ToggleChallengeParams,
)
from nexctf.util.async_utils import call_maybe_async
from nexctf.util.cron import next_fire
from nexctf.util.datetime import event_timezone

logger = logging.getLogger(__name__)

_TASK_HISTORY = 100


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


async def _execute_job_task(
    job: SchedulerJob,
    entry: SchedulerEntry,
    session: AsyncSession,
    redis: Redis,
    now: datetime,
) -> SchedulerTask:
    task = SchedulerTask(job_id=job.id, status=TaskStatus.PENDING, started_at=now)
    session.add(task)
    await session.flush()
    try:
        await call_maybe_async(entry.handler, job, session, redis)
        task.status = TaskStatus.SUCCESS
        task.completed_at = datetime.now(UTC)
    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(UTC)
        task.error = str(exc)[:500]
        logger.exception("Job %s failed", job.id)
    await session.flush()
    return task


async def force_run_job(
    job: SchedulerJob, session: AsyncSession, redis: Redis
) -> SchedulerTask:
    """Execute a job immediately without modifying its scheduled state."""
    now = datetime.now(UTC)

    try:
        entry = scheduler_registry.get(job.job_type)
    except KeyError:
        task = _unregistered_task(job, now)
        session.add(task)
        await session.flush()
        return task

    task = await _execute_job_task(job, entry, session, redis, now)
    await _prune_task_history(session, job)

    if entry.invalidate is not None:
        # The request session commits only once the response has been sent.
        await session.commit()
        await entry.invalidate(redis)
    return task


def _unregistered_task(job: SchedulerJob, now: datetime) -> SchedulerTask:
    """Build the failure record for a job whose type is no longer registered."""
    return SchedulerTask(
        job_id=job.id,
        status=TaskStatus.FAILED,
        started_at=now,
        completed_at=now,
        error=f"unregistered job type: {job.job_type}",
    )


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


def _reschedule(job: SchedulerJob, tz: str) -> None:
    """Advance a cron job to its next fire time, or retire a one-shot job."""
    if not job.cron_expression:
        job.is_active = False
        return
    try:
        job.scheduled_at = next_fire(job.cron_expression, datetime.now(UTC), tz)
    except CronSimError:
        job.is_active = False
        logger.warning(
            "Job %s: unparsable cron %r, deactivated", job.id, job.cron_expression
        )


async def process_scheduled_jobs(session: AsyncSession, redis: Redis) -> None:
    """Execute every due job. Called every 60 s by the worker."""
    now = datetime.now(UTC)

    result = await session.execute(
        select(SchedulerJob)
        .where(
            SchedulerJob.scheduled_at <= now,
            SchedulerJob.is_active.is_(True),
        )
        .with_for_update(skip_locked=True)
    )
    due_jobs = result.scalars().all()

    if not due_jobs:
        return

    logger.info("Processing %d scheduled job(s)", len(due_jobs))

    tz = event_timezone(await appconfig.fetch_overrides(redis))
    invalidators = set()

    for job in due_jobs:
        try:
            entry = scheduler_registry.get(job.job_type)
        except KeyError:
            session.add(_unregistered_task(job, now))
            job.last_run = now
            _reschedule(job, tz)
            await _prune_task_history(session, job)
            logger.warning("Job %s: unregistered type '%s'", job.id, job.job_type)
            continue

        await _execute_job_task(job, entry, session, redis, now)
        job.last_run = now
        _reschedule(job, tz)
        await _prune_task_history(session, job)
        if entry.invalidate is not None:
            invalidators.add(entry.invalidate)

    await session.commit()

    for invalidate in invalidators:
        await invalidate(redis)


scheduler_registry.register(
    type_name="send_notification",
    handler=handle_send_notification,
    create_schema=SendNotificationParams,
    update_schema=SendNotificationParams,
)
scheduler_registry.register(
    type_name="toggle_challenge",
    handler=handle_toggle_challenge,
    create_schema=ToggleChallengeParams,
    update_schema=ToggleChallengeParams,
    invalidate=invalidate_challenges,
)
