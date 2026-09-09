"""index score_adjustments by team and challenge

Revision ID: b7e41c92a5d3
Revises: e8b2f47c1a90
Create Date: 2026-09-09 13:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e41c92a5d3"
down_revision: str | None = "e8b2f47c1a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_score_adjustments_team_challenge",
        "score_adjustments",
        ["team_id", "challenge_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_score_adjustments_team_challenge", table_name="score_adjustments")
