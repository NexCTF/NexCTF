"""Public team profile endpoint."""

from uuid import UUID

from fastapi import APIRouter
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import (
    OptionalCurrentUserDep,
    RedisDep,
    SessionDep,
    check_scoreboard_visibility,
)
from nexctf.module.team import load_team_read
from nexctf.schema.team import PublicTeamRead

team_router = APIRouter(prefix="/team", tags=["Team"])


@team_router.get("/{team_id}")
async def get_team_profile(
    session: SessionDep,
    redis: RedisDep,
    team_id: UUID,
    user: OptionalCurrentUserDep = None,
) -> Response[PublicTeamRead]:
    """Public team profile: fields, members and challenge progress."""
    check_scoreboard_visibility(user)
    team = await load_team_read(session, redis, team_id)
    if team is None:
        raise NotFoundError()
    return Response(data=team)
