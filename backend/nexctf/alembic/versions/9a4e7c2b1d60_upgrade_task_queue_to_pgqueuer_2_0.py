"""upgrade the task queue to pgqueuer 2.0

Revision ID: 9a4e7c2b1d60
Revises: 2f320b357be4
Create Date: 2026-11-15 12:00:00.000000

"""

from collections.abc import Sequence
from typing import cast

import asyncpg
from alembic import op
from pgqueuer.db import AsyncpgDriver
from sqlalchemy.util import await_only

from nexctf.tasks.queue import DB_SETTINGS, build_queries

# revision identifiers, used by Alembic.
revision: str = "9a4e7c2b1d60"
down_revision: str | None = "2f320b357be4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _driver() -> AsyncpgDriver:
    """Wrap the migration's own asyncpg connection, inside its transaction."""
    return AsyncpgDriver(
        cast(asyncpg.Connection, op.get_bind().connection.driver_connection)
    )


def upgrade() -> None:
    """Converge the queue schema onto pgqueuer 2.0's (statistics index)."""
    await_only(build_queries(_driver()).apply_upgrade())


def downgrade() -> None:
    """Drop the statistics index pgqueuer 2.0 added."""
    op.execute(
        f"DROP INDEX IF EXISTS {DB_SETTINGS.db_schema}.pgqueuer_statistics_created"
    )
