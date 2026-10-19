"""Core crons keeping the task queue and session tables bounded."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.db import get_db_context
from nexctf.module.session import purge_expired_access
from nexctf.plugins.declare import CronDef, Plugin
from nexctf.tasks.queue import DB_SETTINGS

RETENTION = timedelta(days=30)


async def purge_old_jobs(session: AsyncSession) -> None:
    """Delete failed jobs and aggregated log rows older than ``RETENTION``."""
    cutoff = {"cutoff": datetime.now(UTC) - RETENTION}
    names = DB_SETTINGS.qualified
    await session.execute(
        text(
            f"DELETE FROM {names.queue_table}"
            " WHERE status = 'failed' AND updated < :cutoff"
        ),
        cutoff,
    )
    await session.execute(
        text(
            f"DELETE FROM {names.queue_table_log}"
            " WHERE aggregated AND created < :cutoff"
        ),
        cutoff,
    )


async def _purge_jobs_cron() -> None:
    async with get_db_context() as session:
        await purge_old_jobs(session)


async def _purge_sessions_cron() -> None:
    async with get_db_context() as session:
        await purge_expired_access(session)


plugin = Plugin(
    crons=[
        CronDef("purge_task_queue", "0 3 * * *", _purge_jobs_cron),
        CronDef("purge_expired_sessions", "30 3 * * *", _purge_sessions_cron),
    ]
)
