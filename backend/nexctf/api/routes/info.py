"""Consolidated info endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi_toolsets.schemas import Response
from sqlalchemy import func, select

from nexctf.api.dep import AdminAuthDep, CurrentUserDep, RedisDep, SessionDep
from nexctf.model import (
    Challenge,
    HintUnlock,
    Submission,
    Team,
    User,
)
from nexctf.module.info import get_public_info, get_version_info
from nexctf.schema import PublicUserRead
from nexctf.schema.info import AdminStats, PublicInfo
from nexctf.util.sql import count_of

info_router = APIRouter(prefix="/info", tags=["info"])


@info_router.get("")
async def public_info(
    session: SessionDep,
    redis: RedisDep,
) -> Response[PublicInfo]:
    return Response(data=await get_public_info(session, redis))


@info_router.get("/me")
async def me_info(
    user: CurrentUserDep,
) -> Response[PublicUserRead]:
    return Response(data=PublicUserRead.model_validate(user))


@info_router.get("/admin", dependencies=[AdminAuthDep])
async def admin_info(
    session: SessionDep,
    redis: RedisDep,
) -> Response[AdminStats]:
    (
        user_count,
        team_count,
        challenge_count,
        submission_count,
        correct_submission_count,
        hint_unlock_count,
        hint_cost_spent,
    ) = (
        await session.execute(
            select(
                count_of(User),
                count_of(Team),
                count_of(Challenge),
                count_of(Submission),
                count_of(Submission, Submission.is_correct.is_(True)),
                count_of(HintUnlock),
                select(func.coalesce(func.sum(HintUnlock.cost_paid), 0))
                .select_from(HintUnlock)
                .scalar_subquery(),
            )
        )
    ).one()

    return Response(
        data=AdminStats(
            users=user_count,
            teams=team_count,
            challenges=challenge_count,
            submissions=submission_count,
            correct_submissions=correct_submission_count,
            hint_unlocks=hint_unlock_count,
            hint_cost_spent=hint_cost_spent,
            version=await get_version_info(redis),
        )
    )
