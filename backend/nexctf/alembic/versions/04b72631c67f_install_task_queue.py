"""install the pgqueuer task queue schema

Revision ID: 04b72631c67f
Revises: b4d9c02a7e15
Create Date: 2026-09-25 12:00:00.000000

"""

from collections.abc import Sequence
from typing import cast

import asyncpg
from alembic import op
from pgqueuer.db import AsyncpgDriver
from sqlalchemy.util import await_only

from nexctf.tasks.queue import DB_SETTINGS, build_queries

# revision identifiers, used by Alembic.
revision: str = "04b72631c67f"
down_revision: str | None = "b4d9c02a7e15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _driver() -> AsyncpgDriver:
    """Wrap the migration's own asyncpg connection, inside its transaction."""
    return AsyncpgDriver(
        cast(asyncpg.Connection, op.get_bind().connection.driver_connection)
    )


def upgrade() -> None:
    """Upgrade schema."""
    await_only(build_queries(_driver()).install())


def downgrade() -> None:
    """Downgrade schema."""
    await_only(build_queries(_driver()).uninstall())
    op.execute(f"DROP SCHEMA IF EXISTS {DB_SETTINGS.db_schema}")
