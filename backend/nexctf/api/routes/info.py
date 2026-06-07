"""Consolidated info endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Security
from fastapi_toolsets.schemas import PaginationType, Response
from sqlalchemy import func, select

import nexctf.core.appconfig as appconfig
import nexctf.crud as crud
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.api.security import auth
from nexctf.model import (
    Challenge,
    HintUnlock,
    OAuthProvider,
    Submission,
    Team,
    User,
    UserRole,
)
from nexctf.schema import PublicOAuthProviderRead, PublicUserRead
from nexctf.schema.info import (
    AdminStats,
    BrandingInfo,
    CaptchaInfo,
    CompetitionInfo,
    PublicInfo,
)

info_router = APIRouter(prefix="/info", tags=["info"])


@info_router.get("")
async def public_info(
    session: SessionDep,
    redis: RedisDep,
) -> Response[PublicInfo]:
    overrides = await appconfig.fetch_overrides(redis)

    def get(key: str) -> str:
        return str(appconfig.get_with_overrides(key, overrides))

    branding = BrandingInfo(
        name=get("ctf.name"),
        logo_url=get("appearance.logo_url"),
        favicon_url=get("appearance.favicon_url"),
        primary_color=get("appearance.primary_color"),
    )

    def get_bool(key: str) -> bool:
        return bool(appconfig.get_with_overrides(key, overrides))

    competition = CompetitionInfo(
        description=get("ctf.description"),
        start_time=get("ctf.start_time"),
        end_time=get("ctf.end_time"),
        freeze_time=get("ctf.freeze_time"),
        allow_registration=get_bool("ctf.allow_registration"),
        allow_team_creation=get_bool("ctf.allow_team_creation"),
        team_size=int(appconfig.get_with_overrides("ctf.team_size", overrides)),
    )

    providers = await crud.OAuthProviderCrud.paginate(
        session=session,
        pagination_type=PaginationType.OFFSET,
        filters=[OAuthProvider.is_active.is_(True)],
        items_per_page=50,
        page=1,
        schema=PublicOAuthProviderRead,
    )

    captcha_enabled = bool(appconfig.get_with_overrides("captcha.enabled", overrides))
    if captcha_enabled:
        cap_api_url = get("captcha.cap_api_url").rstrip("/")
        cap_site_key = get("captcha.cap_site_key")
        widget_endpoint = (
            f"{cap_api_url}/{cap_site_key}/" if cap_api_url and cap_site_key else ""
        )
    else:
        widget_endpoint = ""

    return Response(
        data=PublicInfo(
            branding=branding,
            competition=competition,
            oauth_providers=providers.data,
            captcha=CaptchaInfo(
                enabled=captcha_enabled, widget_endpoint=widget_endpoint
            ),
        )
    )


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
