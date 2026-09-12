"""drop the moderator role, promoting existing moderators to admin

Revision ID: d4a9c17e3b52
Revises: b7e41c92a5d3
Create Date: 2026-09-12 08:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a9c17e3b52"
down_revision: str | None = "b7e41c92a5d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = ("admin", "moderator", "user")
_NEW = ("admin", "user")


def _swap_enum(values: Sequence[str]) -> None:
    """Recreate the userrole type; Postgres cannot drop a value in place."""
    labels = ", ".join(f"'{v}'" for v in values)
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute(f"CREATE TYPE userrole AS ENUM ({labels})")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::text::userrole"
    )
    op.execute("DROP TYPE userrole_old")


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'moderator'")
    op.execute(r"""
        UPDATE oauth_server_clients c
        SET allowed_roles = (
            SELECT string_agg(r, ' ' ORDER BY r)
            FROM (
                SELECT DISTINCT
                    CASE WHEN t = 'moderator' THEN 'admin' ELSE t END AS r
                FROM unnest(regexp_split_to_array(trim(c.allowed_roles), '\s+')) AS t
                WHERE t <> ''
            ) s
        )
        WHERE c.allowed_roles LIKE '%moderator%'
    """)
    _swap_enum(_NEW)


def downgrade() -> None:
    """Downgrade schema."""
    # Which admins used to be moderators is not recorded, so they stay admins.
    _swap_enum(_OLD)
