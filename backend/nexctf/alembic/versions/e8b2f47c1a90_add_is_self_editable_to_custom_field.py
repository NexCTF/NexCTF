"""add is_self_editable to custom field definitions

Revision ID: e8b2f47c1a90
Revises: fd17f73c2c52
Create Date: 2026-09-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8b2f47c1a90"
down_revision: str | None = "fd17f73c2c52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "custom_field_definitions",
        sa.Column(
            "is_self_editable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("custom_field_definitions", "is_self_editable")
