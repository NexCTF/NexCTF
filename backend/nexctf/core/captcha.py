"""ALTCHA captcha: self-hosted challenge issuing and verification."""

from __future__ import annotations

import hashlib
import time

import altcha
from redis.asyncio import Redis

from nexctf.core import appconfig
from nexctf.core.config import settings
from nexctf.exceptions import CaptchaInvalidError, CaptchaRequiredError

ALGORITHM = "PBKDF2/SHA-256"
COST = 5000
# Challenge lifetime, and how long a spent solution is remembered.
TTL = 300


def _hmac_secret() -> bytes:
    """Domain-separated ALTCHA signing key derived from SECRET_KEY."""
    return hashlib.blake2b(key=settings.SECRET_KEY.encode(), person=b"altcha").digest()


def create_challenge() -> dict:
    """Build a signed, expiring ALTCHA challenge for the widget to solve."""
    challenge = altcha.create_challenge(
        ALGORITHM,
        COST,
        expires_at=int(time.time()) + TTL,
        hmac_secret=_hmac_secret(),
    )
    return challenge.to_dict()


async def verify_captcha(
    redis: Redis, overrides: dict[str, str], token: str | None
) -> None:
    """Verify an ALTCHA payload, consuming it so it cannot be replayed.

    Args:
        redis: Connection used to record spent solutions.
        overrides: Per-request config snapshot shared across workers.
        token: The base64 ALTCHA payload supplied by the client, if any.
    """
    if not appconfig.get_with_overrides("captcha.enabled", overrides):
        return

    if not token:
        raise CaptchaRequiredError()

    try:
        payload = altcha.Payload.from_base64(token)
    except ValueError, KeyError, TypeError:
        raise CaptchaInvalidError()

    if not altcha.verify_solution(payload, _hmac_secret()).verified:
        raise CaptchaInvalidError()

    if not await redis.set(
        f"captcha:used:{payload.challenge.signature}", 1, nx=True, ex=TTL
    ):
        raise CaptchaInvalidError()
