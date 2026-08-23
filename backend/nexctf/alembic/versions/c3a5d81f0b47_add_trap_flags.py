"""add trap flags

Revision ID: c3a5d81f0b47
Revises: b7d3e9a41c05
Create Date: 2026-08-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3a5d81f0b47"
down_revision: str | None = "b7d3e9a41c05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "questions",
        sa.Column(
            "trap_flags",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "submissions",
        sa.Column("is_trap", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("submissions", "is_trap")
    op.drop_column("questions", "trap_flags")
