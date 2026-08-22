"""index scheduler_tasks by job and created_at

Revision ID: fd17f73c2c52
Revises: b7d3e9a41c05
Create Date: 2026-08-22 10:35:06.313681

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fd17f73c2c52"
down_revision: str | None = "b7d3e9a41c05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_scheduler_tasks_job_created",
        "scheduler_tasks",
        ["job_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_scheduler_tasks_job_created", table_name="scheduler_tasks")
