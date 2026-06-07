"""Admin stats endpoints."""

from fastapi import APIRouter
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import RedisDep, SessionDep
from nexctf.module.stats import get_all_challenge_stats
from nexctf.schema.stats import ChallengeStats

stats_router = APIRouter(prefix="/stats", tags=["Stats"])


@stats_router.get("/challenges")
async def get_challenge_stats(
    session: SessionDep,
    redis: RedisDep,
) -> Response[list[ChallengeStats]]:
    stats = await get_all_challenge_stats(session, redis)
    return Response(data=stats)
