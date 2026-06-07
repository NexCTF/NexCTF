"""Shared Alembic env.py for all nexctf plugins.

Reads plugin config from NEXCTF_PLUGIN_DIR/pyproject.toml under [tool.nexctf.migrations].
"""

from __future__ import annotations

import asyncio
import os
import sys
import tomllib
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

_plugin_dir = Path(os.environ["NEXCTF_PLUGIN_DIR"])
_backend = _plugin_dir.parents[1]  # <plugin>/ → plugins_store/ → backend/
_store = _plugin_dir.parent

for _p in [str(_backend), str(_store)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

with open(_plugin_dir / "pyproject.toml", "rb") as _f:
    _mig = tomllib.load(_f)["tool"]["nexctf"]["migrations"]

_version_table: str = _mig["version_table"]

from nexctf.core.config import settings  # noqa: E402
from nexctf.model import Base  # noqa: E402
from nexctf.plugins.loader import derive_owned_tables  # noqa: E402

_owned_tables: frozenset[str] = derive_owned_tables(_mig.get("models", []))

config = context.config
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
    return str(settings.SQLALCHEMY_DATABASE_URI)


def run_migrations_offline() -> None:
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
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def main() -> None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())


main()
