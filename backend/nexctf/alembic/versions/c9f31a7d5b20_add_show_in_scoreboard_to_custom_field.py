"""add show_in_scoreboard to custom field definitions

Revision ID: c9f31a7d5b20
Revises: b4cddbd88179
Create Date: 2026-07-30 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f31a7d5b20"
down_revision: str | None = "b4cddbd88179"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "custom_field_definitions",
        sa.Column(
            "show_in_scoreboard",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("custom_field_definitions", "show_in_scoreboard")
