"""CAP captcha verification utility.

Reusable across auth endpoints (login, register, etc.).
"""

from __future__ import annotations

import logging

import httpx
from redis.asyncio import Redis

from nexctf.core import appconfig
from nexctf.exceptions import (
    CaptchaInvalidError,
    CaptchaMisconfiguredError,
    CaptchaRequiredError,
)

logger = logging.getLogger(__name__)


async def verify_captcha(redis: Redis, token: str | None) -> None:
    """Verify a CAP captcha token against the configured CAP backend.

    No-ops when captcha.enabled is false.
    """
    overrides = await appconfig.fetch_overrides(redis)

    if not appconfig.get_with_overrides("captcha.enabled", overrides):
        return

    api_url = str(
        appconfig.get_with_overrides("captcha.cap_api_url", overrides)
    ).rstrip("/")
    site_key = str(appconfig.get_with_overrides("captcha.cap_site_key", overrides))
    secret_key = str(appconfig.get_with_overrides("captcha.cap_secret_key", overrides))

    if not api_url or not site_key or not secret_key:
        logger.error(
            "captcha is enabled but cap_api_url / cap_site_key / cap_secret_key are not fully configured"
        )
        raise CaptchaMisconfiguredError()

    if not token:
        raise CaptchaRequiredError()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{api_url}/{site_key}/siteverify",
                json={"secret": secret_key, "response": token},
            )
    except httpx.HTTPError:
        logger.exception("CAP siteverify request failed")
        raise CaptchaMisconfiguredError()

    try:
        data = resp.json()
    except Exception:
        logger.error(
            "CAP siteverify returned non-JSON response (status %s)", resp.status_code
        )
        raise CaptchaMisconfiguredError()

    if not data.get("success"):
        raise CaptchaInvalidError()
