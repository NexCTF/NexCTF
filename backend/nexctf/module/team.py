"""Team payload assembly shared by the me and public team endpoints."""

from collections.abc import Sequence
from uuid import UUID

from fastapi_toolsets.db import transaction
from redis.asyncio import Redis
from sqlalchemy import ColumnElement, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.model import (
    ChallengeFeedback,
    HintUnlock,
    ScoreAdjustment,
    Submission,
    Team,
    User,
)
from nexctf.model.custom_field import CustomFieldDefinition, CustomFieldValue
from nexctf.model.notification import notification_team_table
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


async def delete_if_abandoned(session: AsyncSession, team_id: UUID) -> bool:
    """Delete a team with no members left and no play or admin history."""
    traces = [
        exists().where(column == team_id)
        for column in (
            User.team_id,
            Submission.team_id,
            ScoreAdjustment.team_id,
            HintUnlock.team_id,
            ChallengeFeedback.team_id,
            notification_team_table.c.team_id,
        )
    ]
    if any((await session.execute(select(*traces))).one()):
        return False
    try:
        async with transaction(session):
            await crud.TeamCrud.delete(session, filters=[Team.id == team_id])
    except IntegrityError:
        return False
    return True


async def load_team_read(
    session: AsyncSession,
    redis: Redis,
    team_id: UUID,
    *,
    overrides: dict[str, str],
    include_rank: bool = True,
    include_members: bool = True,
    include_challenges: bool,
    live: bool = False,
) -> MyTeamRead | None:
    """Load a team with members, stats, public custom fields and global standing.

    Rank/team_count come from the global scoreboard; pass include_rank=False when
    the caller may not view ranking data (hidden scoreboard). Pass
    include_members=False to omit the member list (members are None), and
    include_challenges=False to return no challenge stats. Challenge stats honour
    the scoreboard freeze unless live=True (a team's own members).
    """
    team = await crud.TeamCrud.first(
        session, [Team.id == team_id], load_options=[selectinload(Team.users)]
    )
    if team is None:
        return None
    users = [u for u in team.users if u.is_active]
    stats = (
        await get_team_challenge_stats(
            session, redis, team_id, overrides=overrides, live=live
        )
        if include_challenges
        else []
    )
    custom_fields = await fetch_public_team_fields(session, team_id)
    members: list[PublicTeamMember] | None = None
    if include_members:
        member_fields = await _fetch_public_user_fields(session, [u.id for u in users])
        members = [
            PublicTeamMember(
                id=u.id,
                username=u.username,
                links=u.links or [],
                custom_fields=member_fields.get(u.id, []),
            )
            for u in users
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
        is_disqualified=team.is_disqualified,
        members=members,
        member_count=len(users),
        challenge_stats=stats,
        invite_code=team.invite_code,
        custom_fields=custom_fields,
        rank=rank,
        score=score,
        team_count=team_count,
    )
