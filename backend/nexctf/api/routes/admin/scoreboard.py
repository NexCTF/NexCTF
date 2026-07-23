from uuid import UUID

from fastapi import APIRouter, Query
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import RedisDep, SessionDep
from nexctf.module.scoreboard.cache import get_admin_scoreboard, invalidate
from nexctf.schema import AdminScoreboard

scoreboard_router = APIRouter(prefix="/scoreboard", tags=["Admin Scoreboard"])


@scoreboard_router.get("")
async def get_admin_scoreboard_endpoint(
    session: SessionDep,
    redis: RedisDep,
    bracket: str | None = Query(default=None),
) -> Response[AdminScoreboard]:
    result = await get_admin_scoreboard(session, redis, bracket=bracket)
    return Response(data=result)


@scoreboard_router.post("/invalidate")
async def invalidate_scoreboard_cache(
    redis: RedisDep,
    team_id: UUID | None = None,
) -> Response[None]:
    await invalidate(redis, team_id=team_id)
    return Response(data=None)
