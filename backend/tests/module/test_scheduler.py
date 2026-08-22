"""Tests for the scheduler tick: one-shot retirement and cron rescheduling."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from nexctf.model import User, UserRole
from nexctf.model.scheduler import SchedulerJob, SchedulerTask
from nexctf.module.scheduler import process_scheduled_jobs
from nexctf.plugins.registry import scheduler_registry
from nexctf.schema.scheduler import SendNotificationParams, TaskStatus
from nexctf.util.cron import next_fire


@pytest.fixture
async def owner(db_session: AsyncSession) -> User:
    user = User(username="sched_admin", hashed_password="x", role=UserRole.admin)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def counting_job_type() -> Any:
    """Register a throwaway job type that records every invocation."""
    calls: list[UUID] = []
    type_name = f"test_counter_{uuid4().hex[:8]}"

    async def handler(job: SchedulerJob, session: AsyncSession, redis: Any) -> None:
        calls.append(job.id)

    scheduler_registry.register(
        type_name=type_name,
        handler=handler,
        create_schema=SendNotificationParams,
        update_schema=SendNotificationParams,
    )
    try:
        yield type_name, calls
    finally:
        scheduler_registry._entries.pop(type_name, None)


def _job(owner: User, job_type: str, **kwargs: Any) -> SchedulerJob:
    kwargs.setdefault("params", {})
    return SchedulerJob(
        name="job",
        job_type=job_type,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
        created_by_id=owner.id,
        **kwargs,
    )


async def _task_count(session: AsyncSession, job: SchedulerJob) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(SchedulerTask)
        .where(SchedulerTask.job_id == job.id)
    )
    return result.scalar_one()


async def test_one_shot_job_runs_once_then_retires(
    db_session: AsyncSession, mock_redis: Any, owner: User, counting_job_type: Any
) -> None:
    type_name, calls = counting_job_type
    job = _job(owner, type_name)
    db_session.add(job)
    await db_session.flush()

    await process_scheduled_jobs(db_session, mock_redis)
    await process_scheduled_jobs(db_session, mock_redis)

    assert calls == [job.id]
    assert job.is_active is False
    assert job.last_run is not None


async def test_cron_job_reschedules_and_stays_active(
    db_session: AsyncSession, mock_redis: Any, owner: User, counting_job_type: Any
) -> None:
    type_name, calls = counting_job_type
    job = _job(owner, type_name, cron_expression="*/5 * * * *")
    db_session.add(job)
    await db_session.flush()

    before = datetime.now(UTC)
    await process_scheduled_jobs(db_session, mock_redis)

    assert calls == [job.id]
    assert job.is_active is True
    assert job.scheduled_at > before

    # Not due again yet, so the next tick is a no-op.
    await process_scheduled_jobs(db_session, mock_redis)
    assert calls == [job.id]


async def test_missed_windows_do_not_replay_a_backlog(
    db_session: AsyncSession, mock_redis: Any, owner: User, counting_job_type: Any
) -> None:
    """A worker down for three days catches up with one run, not one per window."""
    type_name, calls = counting_job_type
    job = _job(owner, type_name, cron_expression="*/5 * * * *")
    job.scheduled_at = datetime.now(UTC) - timedelta(days=3)
    db_session.add(job)
    await db_session.flush()

    await process_scheduled_jobs(db_session, mock_redis)

    assert calls == [job.id]
    assert await _task_count(db_session, job) == 1
    assert job.scheduled_at > datetime.now(UTC)


async def test_failing_cron_job_still_reschedules(
    db_session: AsyncSession, mock_redis: Any, owner: User
) -> None:
    type_name = f"test_boom_{uuid4().hex[:8]}"

    async def handler(job: SchedulerJob, session: AsyncSession, redis: Any) -> None:
        raise RuntimeError("boom")

    scheduler_registry.register(
        type_name=type_name,
        handler=handler,
        create_schema=SendNotificationParams,
        update_schema=SendNotificationParams,
    )
    try:
        job = _job(owner, type_name, cron_expression="0 * * * *")
        db_session.add(job)
        await db_session.flush()

        await process_scheduled_jobs(db_session, mock_redis)

        task = (
            await db_session.execute(
                select(SchedulerTask).where(SchedulerTask.job_id == job.id)
            )
        ).scalar_one()
        assert task.status == TaskStatus.FAILED
        assert task.error == "boom"
        assert job.is_active is True
        assert job.scheduled_at > datetime.now(UTC)
    finally:
        scheduler_registry._entries.pop(type_name, None)


async def test_unparsable_cron_deactivates_instead_of_looping(
    db_session: AsyncSession, mock_redis: Any, owner: User, counting_job_type: Any
) -> None:
    """A row edited past schema validation must not re-fire every tick."""
    type_name, calls = counting_job_type
    job = _job(owner, type_name, cron_expression="not a cron")
    db_session.add(job)
    await db_session.flush()

    await process_scheduled_jobs(db_session, mock_redis)
    await process_scheduled_jobs(db_session, mock_redis)

    assert calls == [job.id]
    assert job.is_active is False


async def test_unregistered_job_type_retires_a_one_shot_job(
    db_session: AsyncSession, mock_redis: Any, owner: User
) -> None:
    job = _job(owner, "gone_with_its_plugin")
    db_session.add(job)
    await db_session.flush()

    await process_scheduled_jobs(db_session, mock_redis)

    assert job.is_active is False
    task = (
        await db_session.execute(
            select(SchedulerTask).where(SchedulerTask.job_id == job.id)
        )
    ).scalar_one()
    assert task.status == TaskStatus.FAILED


async def test_unregistered_job_type_keeps_a_cron_job_alive(
    db_session: AsyncSession, mock_redis: Any, owner: User
) -> None:
    """A plugin that is briefly absent must not permanently kill its jobs."""
    job = _job(owner, "gone_with_its_plugin", cron_expression="0 * * * *")
    db_session.add(job)
    await db_session.flush()

    await process_scheduled_jobs(db_session, mock_redis)

    assert job.is_active is True
    assert job.scheduled_at > datetime.now(UTC)
    assert await _task_count(db_session, job) == 1


@pytest.mark.parametrize(
    ("expr", "after", "expected"),
    [
        (
            "*/5 * * * *",
            datetime(2026, 8, 22, 10, 3, tzinfo=UTC),
            datetime(2026, 8, 22, 10, 5, tzinfo=UTC),
        ),
        (
            "0 0 * * *",
            datetime(2026, 8, 22, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 23, 0, 0, tzinfo=UTC),
        ),
    ],
)
def test_next_fire_is_strictly_after(
    expr: str, after: datetime, expected: datetime
) -> None:
    assert next_fire(expr, after) == expected


async def test_force_run_toggle_challenge_invalidates_the_cache(
    db_session: AsyncSession, mock_redis: Any, owner: User
) -> None:
    """Run-now must drop the cached challenge structures, like the tick does."""
    from nexctf.module.scheduler import force_run_job
    from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge

    challenge = StandardChallenge(title="Toggle me", is_active=False)
    db_session.add(challenge)
    await db_session.flush()

    job = _job(
        owner,
        "toggle_challenge",
        params={"challenge_id": str(challenge.id), "make_active": True},
    )
    db_session.add(job)
    await db_session.flush()

    task = await force_run_job(job, db_session, mock_redis)

    assert task.status == TaskStatus.SUCCESS
    assert challenge.is_active is True
    assert mock_redis.delete.called


async def test_a_second_worker_skips_jobs_the_first_is_holding(
    db_session: AsyncSession,
    worker_db_url: str,
    mock_redis: Any,
    owner: User,
    counting_job_type: Any,
) -> None:
    """Concurrent ticks split the due set instead of both claiming the same job."""
    type_name, calls = counting_job_type
    job = _job(owner, type_name)
    db_session.add(job)
    await db_session.commit()

    # db_session stands in for the first worker: claim the due row, hold the lock.
    held = await db_session.execute(
        select(SchedulerJob)
        .where(SchedulerJob.is_active.is_(True))
        .with_for_update(skip_locked=True)
    )
    assert [j.id for j in held.scalars().all()] == [job.id]

    engine = create_async_engine(worker_db_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as other:
            # Fail fast rather than hang if the claim ever stops skipping locks.
            await other.execute(text("SET LOCAL lock_timeout = '5s'"))
            await process_scheduled_jobs(other, mock_redis)
    finally:
        await engine.dispose()

    assert calls == []
