"""case-insensitive unique names and emails

Revision ID: 0118baab8eee
Revises: 7c3e9a51d2f4
Create Date: 2026-10-14 08:46:55.415669

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0118baab8eee"
down_revision: str | None = "7c3e9a51d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = (
    ("uq_teams_name_lower", "teams", "name"),
    ("uq_users_username_lower", "users", "username"),
    ("uq_users_email_lower", "users", "email"),
)


def _duplicates(table: str, column: str) -> list[str]:
    """Values of *column* that collide once lowercased."""
    rows = op.get_bind().execute(
        sa.text(
            f"SELECT string_agg({column}, ', ' ORDER BY {column}) FROM {table} "
            f"WHERE {column} IS NOT NULL GROUP BY lower({column}) HAVING count(*) > 1"
        )
    )
    return [row[0] for row in rows]


def upgrade() -> None:
    """Upgrade schema."""
    clashes = [
        f"{table}.{column}: {group}"
        for _, table, column in _INDEXES
        for group in _duplicates(table, column)
    ]
    if clashes:
        raise RuntimeError(
            "Values differing only by letter case must be renamed before this "
            "upgrade:\n  " + "\n  ".join(clashes)
        )
    for name, table, column in _INDEXES:
        op.create_index(
            name, table, [sa.literal_column(f"lower({column})")], unique=True
        )
        _replace_exact_index(table, column, unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    for name, table, column in reversed(_INDEXES):
        _replace_exact_index(table, column, unique=True)
        op.drop_index(name, table_name=table)


def _replace_exact_index(table: str, column: str, *, unique: bool) -> None:
    """Recreate the plain ``ix_<table>_<column>`` index as unique or not."""
    name = op.f(f"ix_{table}_{column}")
    op.drop_index(name, table_name=table)
    op.create_index(name, table, [column], unique=unique)
