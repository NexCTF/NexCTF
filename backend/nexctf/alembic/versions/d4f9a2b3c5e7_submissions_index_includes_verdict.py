"""submissions index includes verdict

Revision ID: d4f9a2b3c5e7
Revises: c3e8f1a2b4d6
Create Date: 2026-11-27 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f9a2b3c5e7"
down_revision: str | None = "c3e8f1a2b4d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_submissions_team_question"
_COLUMNS = ["team_id", "question_id"]


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(_INDEX, table_name="submissions")
    op.create_index(_INDEX, "submissions", _COLUMNS, postgresql_include=["is_correct"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(_INDEX, table_name="submissions")
    op.create_index(_INDEX, "submissions", _COLUMNS)
