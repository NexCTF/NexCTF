"""rotate team invite codes

Revision ID: c3e8f1a7b924
Revises: 9a4e7c2b1d60
Create Date: 2026-11-16 00:00:00.000000

"""

import secrets
import string
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8f1a7b924"
down_revision: str | None = "9a4e7c2b1d60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _gen_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def upgrade() -> None:
    """Replace every team's invite code with a 16-character one."""
    bind = op.get_bind()
    ids = bind.execute(sa.text("SELECT id FROM teams")).scalars()
    rows = [{"code": _gen_code(), "id": team_id} for team_id in ids]
    if rows:
        bind.execute(
            sa.text("UPDATE teams SET invite_code = :code WHERE id = :id"), rows
        )


def downgrade() -> None:
    """Rotated codes cannot be restored; they stay valid as they are."""
