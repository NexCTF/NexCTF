"""Helpers for the development fixtures."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from nexctf.core.config import settings
from nexctf.model import ConfigEntry


def stored_config_keys() -> set[str]:
    """Config keys already in the database, which fixtures must not overwrite."""

    async def fetch() -> set[str]:
        engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
        try:
            async with engine.connect() as conn:
                return set((await conn.execute(select(ConfigEntry.key))).scalars())
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(fetch())).result()
