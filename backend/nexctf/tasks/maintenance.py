"""Core crons keeping the task queue and session tables bounded."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.db import get_db_context
from nexctf.model import File
from nexctf.module.session import purge_expired_access
from nexctf.plugins.declare import CronDef, Plugin
from nexctf.tasks.queue import DB_SETTINGS
from nexctf.util.upload import stored_sha256

RETENTION = timedelta(days=30)
HASH_BATCH = 50


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


async def hash_stored_files(session: AsyncSession, limit: int = HASH_BATCH) -> int:
    """Fill the SHA-256 of up to *limit* files stored without one; return how many."""
    files = (
        await session.scalars(select(File).where(File.sha256.is_(None)).limit(limit))
    ).all()
    for file in files:
        file.sha256 = await stored_sha256(file.s3_key)
    return len(files)


async def _hash_files_cron() -> None:
    async with get_db_context() as session:
        await hash_stored_files(session)


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
        CronDef("hash_stored_files", "*/10 * * * *", _hash_files_cron),
    ]
)
