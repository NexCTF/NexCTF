"""add bracket to team

Revision ID: b4cddbd88179
Revises: e4736208aa5d
Create Date: 2026-07-23 13:05:57.317219

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4cddbd88179"
down_revision: str | None = "e4736208aa5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "teams",
        sa.Column("bracket", sa.String(length=64), nullable=True),
    )
    op.create_index(op.f("ix_teams_bracket"), "teams", ["bracket"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_teams_bracket"), table_name="teams")
    op.drop_column("teams", "bracket")
