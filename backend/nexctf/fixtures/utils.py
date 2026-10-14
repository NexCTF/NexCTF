"""Helpers for the development fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from nexctf.core.config import settings
from nexctf.model import ConfigEntry, Submission


def _query[T](run: Callable[[AsyncConnection], Awaitable[T]]) -> T:
    """Run *run* on a throwaway connection, outside the fixture loader's loop."""

    async def fetch() -> T:
        engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
        try:
            async with engine.connect() as conn:
                return await run(conn)
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(fetch())).result()


def stored_config_keys() -> set[str]:
    """Config keys already in the database, which fixtures must not overwrite."""

    async def run(conn: AsyncConnection) -> set[str]:
        return set((await conn.execute(select(ConfigEntry.key))).scalars())

    return _query(run)


def earliest_submission() -> datetime | None:
    """Timestamp of the oldest stored submission, if any."""

    async def run(conn: AsyncConnection) -> datetime | None:
        return await conn.scalar(select(func.min(Submission.created_at)))

    return _query(run)
