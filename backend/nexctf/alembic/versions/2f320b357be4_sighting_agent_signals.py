"""sighting agent signals

Revision ID: 2f320b357be4
Revises: b3d9e1f2a4c5
Create Date: 2026-11-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f320b357be4"
down_revision: str | None = "b3d9e1f2a4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_agent_sightings",
        sa.Column("signature_agent", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user_agent_sightings",
        sa.Column(
            "platform_mismatch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_agent_sightings", "platform_mismatch")
    op.drop_column("user_agent_sightings", "signature_agent")
