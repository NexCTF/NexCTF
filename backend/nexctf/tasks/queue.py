"""PgQueuer settings and the transactional ``enqueue`` helper."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Self

import asyncpg
from pgqueuer import Queries
from pgqueuer.adapters.persistence.qb import (
    DBSettings,
    QueryBuilderEnvironment,
    QueryQueueBuilder,
    QuerySchedulerBuilder,
)
from pgqueuer.core.tm import TaskManager
from pgqueuer.ports.driver import Driver
from pydantic import BaseModel
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.config import settings
from nexctf.plugins.declare import TaskDef
from nexctf.plugins.registry import task_registry

DB_SETTINGS = DBSettings(db_schema="pgqueuer")


def build_queries(driver: Driver) -> Queries:
    """Return PgQueuer queries bound to the NexCTF queue schema."""
    return Queries(
        driver,
        qbe=QueryBuilderEnvironment(DB_SETTINGS),
        qbq=QueryQueueBuilder(DB_SETTINGS),
        qbs=QuerySchedulerBuilder(DB_SETTINGS),
    )


async def connect(url: str | None = None) -> asyncpg.Connection:
    """Open a dedicated asyncpg connection, to the application database by default."""
    sa_url = make_url(url or str(settings.SQLALCHEMY_DATABASE_URI))
    dsn = sa_url.set(drivername="postgresql").render_as_string(hide_password=False)
    return await asyncpg.connect(dsn)


class SessionDriver:
    """PgQueuer driver running its queries in a SQLAlchemy session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._shutdown = asyncio.Event()

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        conn = await self._session.connection()
        result = await conn.exec_driver_sql(query, args or None)
        return [dict(row) for row in result.mappings()]

    async def execute(self, query: str, *args: object) -> str:
        conn = await self._session.connection()
        await conn.exec_driver_sql(query, args or None)
        return ""

    async def notify(self, channel: str, payload: str) -> None:
        await self.execute("SELECT pg_notify($1, $2)", channel, payload)

    async def add_listener(
        self, channel: str, callback: Callable[[str | bytes | bytearray], None]
    ) -> None:
        raise NotImplementedError("a session driver cannot LISTEN")

    @property
    def shutdown(self) -> asyncio.Event:
        return self._shutdown

    @property
    def tm(self) -> TaskManager:
        return TaskManager()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None: ...


async def enqueue(
    session: AsyncSession,
    task: TaskDef,
    payload: BaseModel | None = None,
    *,
    dedupe_key: str | None = None,
    delay: timedelta | None = None,
) -> int | None:
    """Queue ``task`` in the session's transaction; it runs once that commits.

    Args:
        session: The session whose transaction the job joins.
        task: A task registered by a loaded plugin.
        payload: An instance of the task's ``payload_schema``.
        dedupe_key: Skip the job while another with this key is queued or running.
        delay: Run no earlier than this long after commit.

    Returns:
        The job id, or None when ``dedupe_key`` matched a live job.

    Raises:
        TypeError: If ``payload`` does not match the task's ``payload_schema``.
        LookupError: If ``task`` was not registered by a loaded plugin.
    """
    schema = task.payload_schema
    if (payload is None) != (schema is None) or (
        schema is not None and not isinstance(payload, schema)
    ):
        raise TypeError(f"task {task.name!r} expects a {schema!r} payload")
    name = task_registry.name_of(task)
    (job_id,) = await build_queries(SessionDriver(session)).enqueue(
        name,
        payload.model_dump_json().encode() if payload is not None else None,
        execute_after=delay,
        dedupe_key=dedupe_key,
        on_conflict="skip",
    )
    return job_id
