"""Public team profile endpoint."""

from uuid import UUID

from fastapi import APIRouter
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import (
    ConfigDep,
    OptionalCurrentUserDep,
    RedisDep,
    SessionDep,
    check_scoreboard_visibility,
)
from nexctf.core import appconfig
from nexctf.module.team import load_team_read
from nexctf.schema.team import PublicTeamRead

team_router = APIRouter(prefix="/team", tags=["Team"])


@team_router.get("/{team_id}")
async def get_team_profile(
    session: SessionDep,
    redis: RedisDep,
    team_id: UUID,
    overrides: ConfigDep,
    user: OptionalCurrentUserDep = None,
) -> Response[PublicTeamRead]:
    """Public team profile: fields, members and challenge progress."""
    check_scoreboard_visibility(user, overrides)
    show_members = appconfig.get_with_overrides(
        "visibility.show_team_members", overrides, sanitize=False
    )
    team = await load_team_read(
        session,
        redis,
        team_id,
        overrides=overrides,
        include_members=bool(show_members),
    )
    if team is None:
        raise NotFoundError()
    return Response(data=team)
