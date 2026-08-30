"""Shared Alembic env.py for all nexctf plugins."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from nexctf.core.config import settings
from nexctf.model import Base

config = context.config

_version_table: str = config.attributes["version_table"]
_owned_tables: frozenset[str] = config.attributes["owned_tables"]

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Restrict autogenerate to tables owned by this plugin."""
    if type_ == "table":
        return name in _owned_tables
    if hasattr(obj, "table"):
        return obj.table.name in _owned_tables
    return True


def get_url() -> str:
    """Return the database URL migrations run against."""
    return str(settings.SQLALCHEMY_DATABASE_URI)


def run_migrations_offline() -> None:
    """Emit migrations as SQL without a live connection."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
        version_table=_version_table,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on an established connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
        version_table=_version_table,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Open an async engine and run migrations through it."""
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def main() -> None:
    """Dispatch to offline or online migration mode."""
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())


main()
