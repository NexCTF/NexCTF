"""Team payload assembly shared by the me and public team endpoints."""

import asyncio
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.model import Team
from nexctf.model.custom_field import CustomFieldDefinition, CustomFieldValue
from nexctf.module.stats import get_team_challenge_stats
from nexctf.schema.custom_field import PublicCustomFieldValue
from nexctf.schema.stats import TeamChallengeStats
from nexctf.schema.team import MyTeamRead, PublicTeamMember


async def fetch_public_team_fields(
    session: AsyncSession, team_id: UUID
) -> list[PublicCustomFieldValue]:
    """Return a team's public custom-field values."""
    rows = await crud.CustomFieldValueCrud.get_multi(
        session=session,
        filters=[
            CustomFieldValue.team_id == team_id,
            CustomFieldDefinition.is_public.is_(True),
        ],
        joins=[
            (
                CustomFieldDefinition,
                CustomFieldValue.definition_id == CustomFieldDefinition.id,
            )
        ],
        order_by=CustomFieldDefinition.name,
    )
    return [
        PublicCustomFieldValue(
            name=v.definition.name,
            label=v.definition.label,
            field_type=v.definition.field_type,
            value=v.value,
        )
        for v in rows
    ]


def build_team_read(
    team: Team,
    members: list[PublicTeamMember],
    stats: list[TeamChallengeStats],
    custom_fields: list[PublicCustomFieldValue] | None = None,
) -> MyTeamRead:
    """Assemble the full team payload (public endpoints strip invite_code via schema)."""
    return MyTeamRead(
        id=team.id,
        name=team.name,
        country=team.country,
        bracket=team.bracket,
        members=members,
        challenge_stats=stats,
        invite_code=team.invite_code,
        custom_fields=custom_fields or [],
    )


async def load_team_read(
    session: AsyncSession, redis: Redis, team_id: UUID
) -> MyTeamRead | None:
    """Load a team with members, stats and public custom fields; None if missing."""
    team, stats, custom_fields = await asyncio.gather(
        crud.TeamCrud.first(
            session, [Team.id == team_id], load_options=[selectinload(Team.users)]
        ),
        get_team_challenge_stats(session, redis, team_id),
        fetch_public_team_fields(session, team_id),
    )
    if team is None:
        return None
    members = [PublicTeamMember(id=u.id, username=u.username) for u in team.users]
    return build_team_read(team, members, stats, custom_fields)
