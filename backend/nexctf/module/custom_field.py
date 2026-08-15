"""Custom field writes shared by the admin user and team endpoints."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import CustomFieldValue


async def create_custom_field_values(
    session: AsyncSession,
    values: dict[UUID, str | None],
    *,
    user_id: UUID | None = None,
    team_id: UUID | None = None,
) -> None:
    """Insert custom field values for a freshly created user or team.

    Runs in the caller's session so the rows land in the same transaction as
    their parent, which keeps the foreign key valid and the create atomic.
    """
    session.add_all(
        [
            CustomFieldValue(
                definition_id=definition_id,
                user_id=user_id,
                team_id=team_id,
                value=value,
            )
            for definition_id, value in values.items()
            if value
        ]
    )
    await session.flush()
