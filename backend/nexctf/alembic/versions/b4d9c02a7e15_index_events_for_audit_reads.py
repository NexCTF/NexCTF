"""index events for the audit and session reads

Revision ID: b4d9c02a7e15
Revises: c3f8a1d2e4b7
Create Date: 2026-09-18 09:12:44.118203

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d9c02a7e15"
down_revision: str | None = "c3f8a1d2e4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_events_type_created", "events", ["event_type", "created_at"])
    op.create_index("ix_events_created", "events", ["created_at"])
    op.create_index("ix_events_actor_created", "events", ["actor_id", "created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_events_actor_created", table_name="events")
    op.drop_index("ix_events_created", table_name="events")
    op.drop_index("ix_events_type_created", table_name="events")
