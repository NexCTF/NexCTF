"""Add scopes to user_tokens

Revision ID: c3f8a1d2e4b7
Revises: d4a9c17e3b52
Create Date: 2026-09-11 00:00:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3f8a1d2e4b7"
down_revision: str | None = "d4a9c17e3b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GROUPS = (
    "challenge",
    "content",
    "notification",
    "plugin",
    "profile",
    "scoreboard",
    "team",
    "token",
    "admin.challenge",
    "admin.config",
    "admin.content",
    "admin.notification",
    "admin.plugin",
    "admin.scoreboard",
    "admin.team",
    "admin.user",
)

_BACKFILL = json.dumps(
    [f"{verb}:{group}" for verb in ("read", "write") for group in _GROUPS]
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_tokens",
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        sa.text("UPDATE user_tokens SET scopes = CAST(:scopes AS jsonb)").bindparams(
            scopes=_BACKFILL
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_tokens", "scopes")
