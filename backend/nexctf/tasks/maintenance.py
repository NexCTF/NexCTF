"""Core cron keeping the task queue tables bounded."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.db import get_db_context
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
    await session.commit()


async def _purge_cron() -> None:
    async with get_db_context() as session:
        await purge_old_jobs(session)


plugin = Plugin(crons=[CronDef("purge_task_queue", "0 3 * * *", _purge_cron)])
