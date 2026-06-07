"""Create challenges_orchestrator table.

Revision ID: 0001
Revises:
Create Date: 2026-04-18
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "challenges_orchestrator",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("orchestrator_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["challenges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("challenges_orchestrator")
