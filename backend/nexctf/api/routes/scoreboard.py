from uuid import UUID

from fastapi import APIRouter, Query
from fastapi_toolsets.exceptions import ForbiddenError, UnauthorizedError
from fastapi_toolsets.schemas import Response

import nexctf.core.appconfig as appconfig
from nexctf.api.dep import OptionalCurrentUserDep, RedisDep, SessionDep
from nexctf.model import User, UserRole
from nexctf.module.scoreboard.cache import (
    get_scoreboard,
    get_scoreboard_history,
    get_team_score,
)
from nexctf.schema import PublicScoreboard, PublicTeamScoreDetail, ScoreboardHistory

scoreboard_router = APIRouter(prefix="/scoreboard", tags=["Scoreboard"])


def _check_scoreboard_visibility(user: "User | None") -> None:
    """Raise if the current user cannot view the scoreboard."""
    visibility = str(appconfig.get("visibility.scoreboard"))
    if user is not None and user.role in (UserRole.admin, UserRole.moderator):
        return
    if visibility == "hidden":
        raise ForbiddenError()
    if visibility == "authenticated" and user is None:
        raise UnauthorizedError()


@scoreboard_router.get("")
async def get_scoreboard_endpoint(
    session: SessionDep,
    redis: RedisDep,
    user: OptionalCurrentUserDep = None,
) -> Response[PublicScoreboard]:
    _check_scoreboard_visibility(user)
    result = await get_scoreboard(session, redis)
    return Response(data=result)


@scoreboard_router.get("/history")
async def get_scoreboard_history_endpoint(
    session: SessionDep,
    redis: RedisDep,
    user: OptionalCurrentUserDep = None,
    limit: int = Query(default=10, ge=1, le=25),
) -> Response[ScoreboardHistory]:
    _check_scoreboard_visibility(user)
    result = await get_scoreboard_history(session, redis, limit=limit)
    return Response(data=result)


@scoreboard_router.get("/team/{team_id}")
async def get_team_score_endpoint(
    session: SessionDep,
    redis: RedisDep,
    team_id: UUID,
    user: OptionalCurrentUserDep = None,
) -> Response[PublicTeamScoreDetail]:
    _check_scoreboard_visibility(user)
    result = await get_team_score(session, redis, team_id)
    return Response(data=result)
