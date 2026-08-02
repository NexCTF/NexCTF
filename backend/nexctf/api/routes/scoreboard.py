from uuid import UUID

from fastapi import APIRouter, Query
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import (
    ConfigDep,
    OptionalCurrentUserDep,
    RedisDep,
    SessionDep,
    check_scoreboard_visibility,
)
from nexctf.module.scoreboard.cache import (
    get_scoreboard,
    get_scoreboard_history,
    get_team_score,
)
from nexctf.schema import PublicScoreboard, PublicTeamScoreDetail, ScoreboardHistory

scoreboard_router = APIRouter(prefix="/scoreboard", tags=["Scoreboard"])


@scoreboard_router.get("")
async def get_scoreboard_endpoint(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    user: OptionalCurrentUserDep = None,
    bracket: str | None = Query(default=None),
) -> Response[PublicScoreboard]:
    check_scoreboard_visibility(user, overrides)
    result = await get_scoreboard(session, redis, overrides=overrides, bracket=bracket)
    return Response(data=result)


@scoreboard_router.get("/history")
async def get_scoreboard_history_endpoint(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    user: OptionalCurrentUserDep = None,
    limit: int = Query(default=10, ge=1, le=25),
    bracket: str | None = Query(default=None),
) -> Response[ScoreboardHistory]:
    check_scoreboard_visibility(user, overrides)
    result = await get_scoreboard_history(
        session, redis, overrides=overrides, limit=limit, bracket=bracket
    )
    return Response(data=result)


@scoreboard_router.get("/team/{team_id}")
async def get_team_score_endpoint(
    session: SessionDep,
    redis: RedisDep,
    team_id: UUID,
    overrides: ConfigDep,
    user: OptionalCurrentUserDep = None,
) -> Response[PublicTeamScoreDetail]:
    check_scoreboard_visibility(user, overrides)
    result = await get_team_score(session, redis, team_id, overrides=overrides)
    return Response(data=result)
