"""Consolidated info endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi_toolsets.schemas import Response
from sqlalchemy import ColumnElement, ScalarSelect, func, select

from nexctf.api.dep import AdminAuthDep, CurrentUserDep, RedisDep, SessionDep
from nexctf.model import (
    Base,
    Challenge,
    HintUnlock,
    Submission,
    Team,
    User,
)
from nexctf.module.info import get_public_info, get_version_info
from nexctf.schema import PublicUserRead
from nexctf.schema.info import AdminStats, PublicInfo

info_router = APIRouter(prefix="/info", tags=["info"])


def _count_of(model: type[Base], *filters: ColumnElement[bool]) -> ScalarSelect[int]:
    """Row count for *model* as a scalar subquery, so counts share one round-trip."""
    return select(func.count()).select_from(model).where(*filters).scalar_subquery()


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
                _count_of(User),
                _count_of(Team),
                _count_of(Challenge),
                _count_of(Submission),
                _count_of(Submission, Submission.is_correct.is_(True)),
                _count_of(HintUnlock),
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
