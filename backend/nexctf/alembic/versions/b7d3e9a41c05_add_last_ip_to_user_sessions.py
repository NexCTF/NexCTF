"""add last_ip to user_sessions

Revision ID: b7d3e9a41c05
Revises: 25660b8d8760
Create Date: 2026-08-21 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d3e9a41c05"
down_revision: str | None = "25660b8d8760"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("user_sessions", sa.Column("last_ip", sa.String(), nullable=True))
    op.execute("UPDATE user_sessions SET last_ip = ip")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_sessions", "last_ip")
