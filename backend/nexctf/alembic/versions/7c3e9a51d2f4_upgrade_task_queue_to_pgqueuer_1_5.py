"""upgrade the task queue to pgqueuer 1.5, link scheduler runs to its jobs

Revision ID: 7c3e9a51d2f4
Revises: 048c21e479cc
Create Date: 2026-10-09 14:30:00.000000

"""

from collections.abc import Sequence
from typing import cast

import asyncpg
import sqlalchemy as sa
from alembic import op
from pgqueuer.db import AsyncpgDriver
from sqlalchemy.util import await_only

from nexctf.tasks.queue import DB_SETTINGS, build_queries

# revision identifiers, used by Alembic.
revision: str = "7c3e9a51d2f4"
down_revision: str | None = "048c21e479cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _driver() -> AsyncpgDriver:
    """Wrap the migration's own asyncpg connection, inside its transaction."""
    return AsyncpgDriver(
        cast(asyncpg.Connection, op.get_bind().connection.driver_connection)
    )


def upgrade() -> None:
    """Converge the queue schema onto pgqueuer's, link scheduler runs to its jobs."""
    await_only(build_queries(_driver()).apply_upgrade())
    op.add_column(
        "scheduler_tasks", sa.Column("queue_job_id", sa.BigInteger(), nullable=True)
    )
    op.execute(
        "UPDATE scheduler_tasks AS t SET queue_job_id = q.id"
        f" FROM {DB_SETTINGS.qualified.queue_table} AS q"
        " WHERE t.status = 'pending'"
        " AND q.dedupe_key = 'scheduler:' || t.job_id::text"
    )
    op.drop_column("scheduler_tasks", "error")


def downgrade() -> None:
    """Restore the scheduler runs' error text; pgqueuer 1.4 runs on the new queue."""
    op.add_column("scheduler_tasks", sa.Column("error", sa.String(), nullable=True))
    op.drop_column("scheduler_tasks", "queue_job_id")
