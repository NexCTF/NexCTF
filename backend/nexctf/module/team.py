"""Team payload assembly shared by the me and public team endpoints."""

from collections.abc import Sequence
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.model import Team
from nexctf.model.custom_field import CustomFieldDefinition, CustomFieldValue
from nexctf.module.scoreboard import get_scoreboard
from nexctf.module.stats import get_team_challenge_stats
from nexctf.schema.custom_field import PublicCustomFieldValue
from nexctf.schema.team import MyTeamRead, PublicTeamMember


async def _fetch_public_fields(
    session: AsyncSession, owner_filter: ColumnElement[bool]
) -> Sequence[CustomFieldValue]:
    """Return public custom-field values matching an owner filter."""
    return await crud.CustomFieldValueCrud.get_multi(
        session=session,
        filters=[owner_filter, CustomFieldDefinition.is_public.is_(True)],
        joins=[
            (
                CustomFieldDefinition,
                CustomFieldValue.definition_id == CustomFieldDefinition.id,
            )
        ],
        order_by=CustomFieldDefinition.name,
    )


def _to_public(value: CustomFieldValue) -> PublicCustomFieldValue:
    return PublicCustomFieldValue(
        name=value.definition.name,
        label=value.definition.label,
        field_type=value.definition.field_type,
        value=value.value,
    )


async def fetch_public_team_fields(
    session: AsyncSession, team_id: UUID
) -> list[PublicCustomFieldValue]:
    """Return a team's public custom-field values."""
    rows = await _fetch_public_fields(session, CustomFieldValue.team_id == team_id)
    return [_to_public(v) for v in rows]


async def _fetch_public_user_fields(
    session: AsyncSession, user_ids: list[UUID]
) -> dict[UUID, list[PublicCustomFieldValue]]:
    """Return public custom-field values per user."""
    if not user_ids:
        return {}
    rows = await _fetch_public_fields(session, CustomFieldValue.user_id.in_(user_ids))
    by_user: dict[UUID, list[PublicCustomFieldValue]] = {}
    for row in rows:
        if row.user_id is not None:
            by_user.setdefault(row.user_id, []).append(_to_public(row))
    return by_user


async def load_team_read(
    session: AsyncSession,
    redis: Redis,
    team_id: UUID,
    *,
    overrides: dict[str, str],
    include_rank: bool = True,
    include_members: bool = True,
    live: bool = False,
) -> MyTeamRead | None:
    """Load a team with members, stats, public custom fields and global standing.

    Rank/team_count come from the global scoreboard; pass include_rank=False when
    the caller may not view ranking data (hidden scoreboard). Pass
    include_members=False to omit the member list (members are None). Challenge
    stats honour the scoreboard freeze unless live=True (a team's own members).
    """
    team = await crud.TeamCrud.first(
        session, [Team.id == team_id], load_options=[selectinload(Team.users)]
    )
    if team is None:
        return None
    stats = await get_team_challenge_stats(
        session, redis, team_id, overrides=overrides, live=live
    )
    custom_fields = await fetch_public_team_fields(session, team_id)
    members: list[PublicTeamMember] | None = None
    if include_members:
        member_fields = await _fetch_public_user_fields(
            session, [u.id for u in team.users]
        )
        members = [
            PublicTeamMember(
                id=u.id,
                username=u.username,
                links=u.links or [],
                custom_fields=member_fields.get(u.id, []),
            )
            for u in team.users
        ]
    rank: int | None = None
    score: int | None = None
    team_count = 0
    if include_rank:
        scoreboard = await get_scoreboard(session, redis, overrides=overrides)
        entry = next((e for e in scoreboard.entries if e.team_id == team_id), None)
        rank = entry.rank if entry else None
        score = entry.total if entry else None
        team_count = len(scoreboard.entries)
    return MyTeamRead(
        id=team.id,
        name=team.name,
        country=team.country,
        bracket=team.bracket,
        links=team.links or [],
        members=members,
        member_count=len(team.users),
        challenge_stats=stats,
        invite_code=team.invite_code,
        custom_fields=custom_fields,
        rank=rank,
        score=score,
        team_count=team_count,
    )
