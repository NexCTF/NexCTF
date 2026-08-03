from uuid import UUID

from fastapi import APIRouter, Query
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import (
    BracketDep,
    ConfigDep,
    RedisDep,
    ScoreboardVisibleDep,
    SessionDep,
)
from nexctf.module.scoreboard.cache import (
    get_scoreboard,
    get_scoreboard_history,
    get_team_score,
)
from nexctf.schema import PublicScoreboard, PublicTeamScoreDetail, ScoreboardHistory

scoreboard_router = APIRouter(
    prefix="/scoreboard",
    tags=["Scoreboard"],
    dependencies=[ScoreboardVisibleDep],
)


@scoreboard_router.get("")
async def get_scoreboard_endpoint(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    bracket: BracketDep = None,
) -> Response[PublicScoreboard]:
    result = await get_scoreboard(session, redis, overrides=overrides, bracket=bracket)
    return Response(data=result)


@scoreboard_router.get("/history")
async def get_scoreboard_history_endpoint(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    bracket: BracketDep = None,
    limit: int = Query(default=10, ge=1, le=25),
) -> Response[ScoreboardHistory]:
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
) -> Response[PublicTeamScoreDetail]:
    result = await get_team_score(session, redis, team_id, overrides=overrides)
    return Response(data=result)
