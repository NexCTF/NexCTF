"""team disqualification

Revision ID: b3d9e1f2a4c5
Revises: 63a642891ebe
Create Date: 2026-10-30 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d9e1f2a4c5"
down_revision: str | None = "63a642891ebe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "teams",
        sa.Column(
            "is_disqualified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("teams", "is_disqualified")
