"""Team payload assembly shared by the me and public team endpoints."""

import asyncio
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.model import Team
from nexctf.model.custom_field import CustomFieldDefinition, CustomFieldValue
from nexctf.module.scoreboard import get_scoreboard
from nexctf.module.stats import get_team_challenge_stats
from nexctf.schema.custom_field import PublicCustomFieldValue
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


async def load_team_read(
    session: AsyncSession,
    redis: Redis,
    team_id: UUID,
    *,
    include_rank: bool = True,
    include_members: bool = True,
) -> MyTeamRead | None:
    """Load a team with members, stats, public custom fields and global standing.

    Rank/team_count come from the global scoreboard; pass include_rank=False when
    the caller may not view ranking data (hidden scoreboard). Pass
    include_members=False to omit the member list (members are None).
    """
    team = await crud.TeamCrud.first(
        session, [Team.id == team_id], load_options=[selectinload(Team.users)]
    )
    if team is None:
        return None
    stats, custom_fields = await asyncio.gather(
        get_team_challenge_stats(session, redis, team_id),
        fetch_public_team_fields(session, team_id),
    )
    rank: int | None = None
    score: int | None = None
    team_count = 0
    if include_rank:
        scoreboard = await get_scoreboard(session, redis)
        entry = next((e for e in scoreboard.entries if e.team_id == team_id), None)
        rank = entry.rank if entry else None
        score = entry.total if entry else None
        team_count = len(scoreboard.entries)
    return MyTeamRead(
        id=team.id,
        name=team.name,
        country=team.country,
        bracket=team.bracket,
        members=[PublicTeamMember(id=u.id, username=u.username) for u in team.users]
        if include_members
        else None,
        member_count=len(team.users),
        challenge_stats=stats,
        invite_code=team.invite_code,
        custom_fields=custom_fields,
        rank=rank,
        score=score,
        team_count=team_count,
    )
