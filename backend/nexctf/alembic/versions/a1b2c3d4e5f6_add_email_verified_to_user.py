"""Add email_verified to user

Revision ID: a1b2c3d4e5f6
Revises: 16800b9e9b86
Create Date: 2026-06-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "16800b9e9b86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Existing users predate the verification flow; treat them as verified so
    # the login gate does not lock anyone out.
    op.execute("UPDATE users SET email_verified = true")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "email_verified")
