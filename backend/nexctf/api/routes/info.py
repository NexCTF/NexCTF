"""Consolidated info endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Security
from fastapi_toolsets.schemas import Response
from sqlalchemy import func, select

from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.api.security import auth
from nexctf.model import (
    Challenge,
    HintUnlock,
    Submission,
    Team,
    User,
    UserRole,
)
from nexctf.module.info import get_public_info
from nexctf.schema import PublicUserRead
from nexctf.schema.info import AdminStats, PublicInfo

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


@info_router.get("/admin")
async def admin_info(
    session: SessionDep,
    _: User = Security(auth.require(role=UserRole.admin)),
) -> Response[AdminStats]:
    r_users, r_teams, r_challenges, r_subs, r_correct, r_hints = await asyncio.gather(
        session.execute(select(func.count()).select_from(User)),
        session.execute(select(func.count()).select_from(Team)),
        session.execute(select(func.count()).select_from(Challenge)),
        session.execute(select(func.count()).select_from(Submission)),
        session.execute(
            select(func.count())
            .select_from(Submission)
            .where(Submission.is_correct.is_(True))
        ),
        session.execute(
            select(
                func.count(), func.coalesce(func.sum(HintUnlock.cost_paid), 0)
            ).select_from(HintUnlock)
        ),
    )
    user_count: int = r_users.scalar_one()
    team_count: int = r_teams.scalar_one()
    challenge_count: int = r_challenges.scalar_one()
    submission_count: int = r_subs.scalar_one()
    correct_submission_count: int = r_correct.scalar_one()
    hint_unlock_count, hint_cost_spent = r_hints.one()

    return Response(
        data=AdminStats(
            users=user_count,
            teams=team_count,
            challenges=challenge_count,
            submissions=submission_count,
            correct_submissions=correct_submission_count,
            hint_unlocks=hint_unlock_count,
            hint_cost_spent=hint_cost_spent,
        )
    )
