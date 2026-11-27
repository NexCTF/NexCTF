"""challenge files and file hash

Revision ID: a9c4e2f17b30
Revises: d7b2a4c9e135
Create Date: 2026-11-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c4e2f17b30"
down_revision: str | None = "d7b2a4c9e135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_QUESTION_FILES_FKS = (
    ("question_files_question_id_fkey", "questions", "question_id"),
    ("question_files_file_id_fkey", "stored_files", "file_id"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "challenge_files",
        sa.Column("challenge_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["challenges.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["file_id"], ["stored_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("challenge_id", "file_id"),
    )
    for table in ("challenge_files", "question_files"):
        op.create_index(op.f(f"ix_{table}_file_id"), table, ["file_id"], unique=False)
    op.add_column("stored_files", sa.Column("sha256", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_stored_files_sha256"), "stored_files", ["sha256"], unique=False
    )
    for name, target, column in _QUESTION_FILES_FKS:
        op.drop_constraint(name, "question_files", type_="foreignkey")
        op.create_foreign_key(
            name, "question_files", target, [column], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    """Downgrade schema."""
    for name, target, column in _QUESTION_FILES_FKS:
        op.drop_constraint(name, "question_files", type_="foreignkey")
        op.create_foreign_key(name, "question_files", target, [column], ["id"])
    op.drop_index(op.f("ix_stored_files_sha256"), table_name="stored_files")
    op.drop_index(op.f("ix_question_files_file_id"), table_name="question_files")
    op.drop_column("stored_files", "sha256")
    op.drop_table("challenge_files")
