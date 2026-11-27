"""submission correct at submit

Revision ID: e2a7c4b9d013
Revises: d4f9a2b3c5e7
Create Date: 2026-11-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2a7c4b9d013"
down_revision: str | None = "d4f9a2b3c5e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_submissions_team_question"
_COLUMNS = ["team_id", "question_id"]


def upgrade() -> None:
    """Upgrade schema.

    Existing rows take their current verdict, the verdict they were sent with
    not being recorded before this revision.
    """
    op.add_column(
        "submissions",
        sa.Column(
            "correct_at_submit",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.execute("UPDATE submissions SET correct_at_submit = is_correct")
    op.drop_index(_INDEX, table_name="submissions")
    op.create_index(
        _INDEX,
        "submissions",
        _COLUMNS,
        postgresql_include=["is_correct", "correct_at_submit"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(_INDEX, table_name="submissions")
    op.create_index(_INDEX, "submissions", _COLUMNS, postgresql_include=["is_correct"])
    op.drop_column("submissions", "correct_at_submit")
