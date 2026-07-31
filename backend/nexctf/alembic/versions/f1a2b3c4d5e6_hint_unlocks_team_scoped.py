"""hint unlocks are team scoped

Revision ID: f1a2b3c4d5e6
Revises: c9f31a7d5b20
Create Date: 2026-07-31 10:12:04.118322

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "c9f31a7d5b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "hint_unlocks",
        sa.Column("team_id", sa.Uuid(), nullable=True),
    )
    op.drop_constraint("uq_hint_unlock", "hint_unlocks", type_="unique")
    op.execute(
        "UPDATE hint_unlocks SET team_id = users.team_id "
        "FROM users WHERE users.id = hint_unlocks.user_id"
    )
    bind = op.get_bind()
    # Unlocks by teamless users never counted towards any score.
    orphaned = bind.execute(
        sa.text("DELETE FROM hint_unlocks WHERE team_id IS NULL")
    ).rowcount
    # Keep the earliest unlock per team: that is when the team paid.
    duplicated = bind.execute(
        sa.text(
            "DELETE FROM hint_unlocks WHERE id IN ("
            "  SELECT id FROM ("
            "    SELECT id, ROW_NUMBER() OVER ("
            "      PARTITION BY team_id, hint_id ORDER BY created_at, id"
            "    ) AS rn FROM hint_unlocks"
            "  ) ranked WHERE rn > 1"
            ")"
        )
    ).rowcount
    print(f"dropped {orphaned} teamless and {duplicated} duplicate hint unlock(s)")
    op.alter_column("hint_unlocks", "team_id", nullable=False)
    op.create_foreign_key(None, "hint_unlocks", "teams", ["team_id"], ["id"])
    op.drop_column("hint_unlocks", "user_id")
    op.create_unique_constraint(
        "uq_hint_unlock", "hint_unlocks", ["team_id", "hint_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "hint_unlocks",
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )
    # Attribute each unlock to an arbitrary member of the paying team.
    op.execute(
        "UPDATE hint_unlocks SET user_id = u.id FROM ("
        "  SELECT DISTINCT ON (team_id) team_id, id FROM users ORDER BY team_id, id"
        ") u WHERE u.team_id = hint_unlocks.team_id"
    )
    op.execute("DELETE FROM hint_unlocks WHERE user_id IS NULL")
    op.alter_column("hint_unlocks", "user_id", nullable=False)
    op.create_foreign_key(None, "hint_unlocks", "users", ["user_id"], ["id"])
    op.drop_constraint("uq_hint_unlock", "hint_unlocks", type_="unique")
    op.drop_column("hint_unlocks", "team_id")
    op.create_unique_constraint(
        "uq_hint_unlock", "hint_unlocks", ["user_id", "hint_id"]
    )
