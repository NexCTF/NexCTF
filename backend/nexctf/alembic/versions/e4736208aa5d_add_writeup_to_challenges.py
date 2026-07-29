"""Add writeup to challenges

Revision ID: e4736208aa5d
Revises: e40c10e29caf
Create Date: 2026-07-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4736208aa5d"
down_revision: str | None = "e40c10e29caf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("challenges", sa.Column("writeup", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("challenges", "writeup")
