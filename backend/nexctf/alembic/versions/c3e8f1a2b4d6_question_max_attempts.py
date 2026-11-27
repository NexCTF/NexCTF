"""question max attempts

Revision ID: c3e8f1a2b4d6
Revises: a9c4e2f17b30
Create Date: 2026-11-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8f1a2b4d6"
down_revision: str | None = "a9c4e2f17b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("questions", sa.Column("max_attempts", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("questions", "max_attempts")
