"""inline category and tags as normalised labels

Revision ID: d5e1c07a3f92
Revises: 931b491bef60
Create Date: 2026-08-03 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5e1c07a3f92"
down_revision: str | None = "931b491bef60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LABELS = postgresql.ARRAY(sa.String(length=64))


def _norm(column: str) -> str:
    """SQL mirror of nexctf.util.pydantic.normalise_label."""
    return f"nullif(regexp_replace(btrim(lower({column})), '\\s+', ' ', 'g'), '')"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "challenges", sa.Column("category", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "challenges",
        sa.Column("tags", _LABELS, server_default="{}", nullable=False),
    )
    op.add_column(
        "questions",
        sa.Column("tags", _LABELS, server_default="{}", nullable=False),
    )

    op.execute(
        f"""
        UPDATE challenges c
        SET category = {_norm("cc.name")}
        FROM challenge_categories cc
        WHERE c.category_id = cc.id
        """
    )
    for table, join in (("challenges", "challenge"), ("questions", "question")):
        label = _norm("tag.name")
        op.execute(
            f"""
            UPDATE {table} t
            SET tags = COALESCE((
                SELECT array_agg(DISTINCT {label} ORDER BY {label})
                FROM {join}_tags jt
                JOIN tag ON tag.id = jt.tag_id
                WHERE jt.{join}_id = t.id AND {label} IS NOT NULL
            ), '{{}}')
            """
        )
    op.execute(f"UPDATE teams SET bracket = {_norm('bracket')}")

    op.create_index(
        op.f("ix_challenges_category"), "challenges", ["category"], unique=False
    )

    op.drop_table("challenge_tags")
    op.drop_table("question_tags")
    op.drop_column("challenges", "category_id")
    op.drop_table("tag")
    op.drop_table("challenge_categories")


def downgrade() -> None:
    """Downgrade schema.

    Not supported: per-tag colour, tag descriptions and category slugs are
    dropped by the upgrade and cannot be reconstructed.
    """
    raise NotImplementedError("irreversible: tag colours and category slugs are lost")
