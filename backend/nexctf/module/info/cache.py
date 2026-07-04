"""Redis caching for the public CTF info endpoint."""

from __future__ import annotations

from datetime import timedelta

from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

import nexctf.core.appconfig as appconfig
import nexctf.crud as crud
from nexctf.core.cache import get_or_compute
from nexctf.model import Link, OAuthProvider
from nexctf.model.link import Visibility
from nexctf.schema import PublicOAuthProviderRead
from nexctf.schema.info import (
    BrandingInfo,
    CaptchaInfo,
    CompetitionInfo,
    PublicInfo,
)
from nexctf.schema.link import PublicLinkRead

_KEY = "info:public"
_TTL = timedelta(seconds=60)

_adapter: TypeAdapter[PublicInfo] = TypeAdapter(PublicInfo)


async def _compute(session: AsyncSession, redis: Redis) -> PublicInfo:
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
        require_email=get_bool("email.enabled"),
        team_size=int(appconfig.get_with_overrides("ctf.team_size", overrides)),
    )

    providers = await crud.OAuthProviderCrud.get_multi(
        session, filters=[OAuthProvider.is_active.is_(True)]
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

    links = await crud.LinkCrud.get_multi(
        session,
        filters=[Link.is_enabled.is_(True), Link.visibility == Visibility.PUBLIC],
    )

    return PublicInfo(
        branding=branding,
        competition=competition,
        oauth_providers=[PublicOAuthProviderRead.model_validate(p) for p in providers],
        captcha=CaptchaInfo(enabled=captcha_enabled, widget_endpoint=widget_endpoint),
        links=[PublicLinkRead.model_validate(link) for link in links],
    )


async def get_public_info(
    session: AsyncSession,
    redis: Redis,
    ttl: timedelta = _TTL,
) -> PublicInfo:
    """Return the cached public CTF info, recomputing when cold."""
    return await get_or_compute(
        redis,
        _KEY,
        _adapter,
        lambda: _compute(session, redis),
        ttl,
    )


async def invalidate(redis: Redis) -> None:
    """Drop the cached public info so the next request recomputes it."""
    await redis.delete(_KEY)
