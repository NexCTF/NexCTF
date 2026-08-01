"""backfill team invite codes

Revision ID: 931b491bef60
Revises: f1a2b3c4d5e6
Create Date: 2026-08-01 00:00:00.000000

"""

import secrets
import string
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "931b491bef60"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _gen_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def upgrade() -> None:
    """Give every team without an invite code a generated one, then require it."""
    bind = op.get_bind()
    ids = bind.execute(
        sa.text("SELECT id FROM teams WHERE invite_code IS NULL")
    ).scalars()
    rows = [{"code": _gen_code(), "id": team_id} for team_id in ids]
    if rows:
        bind.execute(
            sa.text("UPDATE teams SET invite_code = :code WHERE id = :id"), rows
        )
    op.alter_column("teams", "invite_code", nullable=False)


def downgrade() -> None:
    """Backfilled codes are indistinguishable from real ones; only the constraint goes."""
    op.alter_column("teams", "invite_code", nullable=True)
