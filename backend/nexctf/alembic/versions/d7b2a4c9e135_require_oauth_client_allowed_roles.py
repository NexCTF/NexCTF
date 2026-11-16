"""require oauth client allowed roles

Revision ID: d7b2a4c9e135
Revises: c3e8f1a7b924
Create Date: 2026-11-16 00:00:01.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7b2a4c9e135"
down_revision: str | None = "c3e8f1a7b924"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "oauth_server_clients"


def upgrade() -> None:
    """Restrict clients that listed no role to admins, then require the list."""
    op.execute(
        sa.text(
            f"UPDATE {_TABLE} SET allowed_roles = 'admin' "
            "WHERE allowed_roles IS NULL OR btrim(allowed_roles) = ''"
        )
    )
    op.alter_column(_TABLE, "allowed_roles", nullable=False)


def downgrade() -> None:
    """Backfilled lists stay as they are; only the constraint goes."""
    op.alter_column(_TABLE, "allowed_roles", nullable=True)
