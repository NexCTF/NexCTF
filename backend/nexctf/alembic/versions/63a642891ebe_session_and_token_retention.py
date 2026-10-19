"""session and token retention

Revision ID: 63a642891ebe
Revises: 0118baab8eee
Create Date: 2026-10-19 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "63a642891ebe"
down_revision: str | None = "0118baab8eee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_agent_sightings", sa.Column("token_name", sa.String(), nullable=True)
    )
    op.execute(
        "UPDATE user_agent_sightings AS s SET token_name = t.name"
        " FROM user_tokens AS t WHERE s.token_id = t.id"
    )
    with op.get_context().autocommit_block():
        op.create_index(
            op.f("ix_user_sessions_expires_at"),
            "user_sessions",
            ["expires_at"],
            postgresql_concurrently=True,
        )
        op.create_index(
            op.f("ix_user_agent_sightings_token_id"),
            "user_agent_sightings",
            ["token_id"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.drop_index(
            op.f("ix_user_agent_sightings_token_id"),
            table_name="user_agent_sightings",
            postgresql_concurrently=True,
        )
        op.drop_index(
            op.f("ix_user_sessions_expires_at"),
            table_name="user_sessions",
            postgresql_concurrently=True,
        )
    op.drop_column("user_agent_sightings", "token_name")
