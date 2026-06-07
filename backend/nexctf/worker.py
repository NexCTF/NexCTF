"""Standalone scheduler worker.

Run with:
    python -m nexctf.worker

This process must NOT be started inside the API lifespan — it is a separate
container/service. Running multiple replicas of this worker will cause each
due job to fire N times (no distributed locking in v1). Run exactly one replica.
"""

from __future__ import annotations

import asyncio
import logging

from nexctf.core.appconfig import load_from_db
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
        await load_from_db(session, redis)
        load_plugin_registries()

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
