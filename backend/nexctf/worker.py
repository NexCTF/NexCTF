"""Standalone scheduler worker.

Run with:
    python -m nexctf.worker

This process must NOT be started inside the API lifespan.
"""

from __future__ import annotations

import asyncio
import logging

# Imported for its side effect: registers the config definitions.
import nexctf.settings as _  # noqa: F401
from nexctf.core.appconfig import sync_to_redis
from nexctf.core.cache import get_client as get_redis_client
from nexctf.core.db import get_db_context
from nexctf.module.scheduler import process_scheduled_jobs
from nexctf.plugins import load_plugin_registries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_TICK_INTERVAL = 60  # seconds


async def main() -> None:
    redis = get_redis_client()

    async with get_db_context() as session:
        load_plugin_registries()
        await sync_to_redis(session, redis)

    logger.info("Scheduler worker started (tick every %ds)", _TICK_INTERVAL)

    while True:
        async with get_db_context() as session:
            try:
                await process_scheduled_jobs(session, redis)
            except Exception:
                logger.exception("Unhandled error in scheduler tick")
        await asyncio.sleep(_TICK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
