"""Scheduler module: built-in handlers + worker tick function."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model.scheduler import SchedulerJob, SchedulerTask
from nexctf.module.notification import publish_notification
from nexctf.plugins.registry import scheduler_registry
from nexctf.schema.scheduler import (
    SendNotificationParams,
    TaskStatus,
    ToggleChallengeParams,
)
from nexctf.util.async_utils import call_maybe_async

logger = logging.getLogger(__name__)


async def handle_send_notification(
    job: SchedulerJob, session: AsyncSession, redis: Redis
) -> None:
    import nexctf.crud as crud
    from nexctf.schema.notification import (
        AdminNotificationCreate,
        AdminNotificationReadDetail,
    )

    params = SendNotificationParams.model_validate(job.params)

    obj = AdminNotificationCreate(
        title=params.title,
        content=params.content,
        is_broadcast=params.is_broadcast,
        created_by_id=job.created_by_id,
        team_ids=params.team_ids,
    )
    response = await crud.NotificationCrud.create(
        session=session, obj=obj, schema=AdminNotificationReadDetail
    )
    assert response.data is not None
    await publish_notification(
        redis, params.is_broadcast, params.team_ids, response.data.model_dump_json()
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
    entry,
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
        task.completed_at = datetime.now(timezone.utc)
    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        task.error = str(exc)[:500]
        logger.exception("Job %s failed: %s", job.id, exc)
    session.add(task)
    await session.flush()
    return task


async def force_run_job(
    job: SchedulerJob, session: AsyncSession, redis: Redis
) -> SchedulerTask:
    """Execute a job immediately without modifying its scheduled state."""
    now = datetime.now(timezone.utc)

    try:
        entry = scheduler_registry.get(job.job_type)
    except KeyError:
        task = SchedulerTask(
            job_id=job.id,
            status=TaskStatus.FAILED,
            started_at=now,
            completed_at=now,
            error=f"unregistered job type: {job.job_type}",
        )
        session.add(task)
        await session.flush()
        return task

    task = await _execute_job_task(job, entry, session, redis, now)
    if task.status == TaskStatus.SUCCESS:
        logger.info("Force-run of job %s succeeded", job.id)
    return task


async def process_scheduled_jobs(session: AsyncSession, redis: Redis) -> None:
    """Execute all one-shot jobs that are due. Called every 60 s by the worker."""
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(SchedulerJob).where(
            SchedulerJob.scheduled_at <= now,
            SchedulerJob.is_active.is_(True),
        )
    )
    due_jobs = result.scalars().all()

    if not due_jobs:
        return

    logger.info("Processing %d scheduled job(s)", len(due_jobs))

    job_ids = [job.id for job in due_jobs]
    in_flight_result = await session.execute(
        select(SchedulerTask.job_id)
        .where(
            SchedulerTask.job_id.in_(job_ids),
            SchedulerTask.status == TaskStatus.PENDING,
        )
        .distinct()
    )
    in_flight_ids = set(in_flight_result.scalars().all())

    processed_job_ids = []
    structure_changed = False

    for job in due_jobs:
        if job.id in in_flight_ids:
            logger.debug("Job %s already in-flight, skipping", job.id)
            continue

        try:
            entry = scheduler_registry.get(job.job_type)
        except KeyError:
            task = SchedulerTask(
                job_id=job.id,
                status=TaskStatus.FAILED,
                started_at=now,
                completed_at=now,
                error=f"unregistered job type: {job.job_type}",
            )
            session.add(task)
            job.last_run = now
            job.is_active = False
            logger.warning("Job %s: unregistered type '%s'", job.id, job.job_type)
            continue

        await _execute_job_task(job, entry, session, redis, now)
        job.last_run = now
        job.is_active = False
        session.add(job)
        processed_job_ids.append(job.id)
        if job.job_type == "toggle_challenge":
            structure_changed = True

    if processed_job_ids:
        inner = (
            sa.select(
                SchedulerTask.id,
                sa.func.row_number()
                .over(
                    partition_by=SchedulerTask.job_id,
                    order_by=SchedulerTask.created_at.desc(),
                )
                .label("rn"),
            )
            .where(SchedulerTask.job_id.in_(processed_job_ids))
            .subquery()
        )
        await session.execute(
            sa.delete(SchedulerTask).where(
                SchedulerTask.id.in_(sa.select(inner.c.id).where(inner.c.rn > 100))
            )
        )

    await session.commit()

    # A toggled challenge changes is_active, which the cached player challenge
    # structures filter on; invalidate after commit so the change is visible.
    if structure_changed:
        from nexctf.module.challenge import invalidate as invalidate_challenges

        await invalidate_challenges(redis)

    logger.info("Scheduler tick completed")


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
)
