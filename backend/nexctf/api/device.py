"""Device cookies: browsers that already signed in to an account."""

import hashlib
import hmac
import secrets
from uuid import UUID

from fastapi import Request, Response

from nexctf.core.config import settings
from nexctf.model import User

DEVICE_TTL = 180 * 86400
_PATH = f"{settings.API_V1_STR}/auth"


def device_cookie_name(user_id: UUID) -> str:
    """Name of the device cookie for *user_id*, one per account per browser."""
    return f"NexCTF-device-{user_id}"


def _signature(user: User, nonce: str) -> str:
    """HMAC binding *nonce* to *user* at its current session version."""
    key = hashlib.blake2b(key=settings.SECRET_KEY.encode(), person=b"device").digest()
    payload = f"{user.id}.{user.session_version}.{nonce}".encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def set_device_cookie(response: Response, user: User) -> None:
    """Mark this browser as a known device of *user*."""
    nonce = secrets.token_urlsafe(16)
    response.set_cookie(
        device_cookie_name(user.id),
        f"{nonce}.{_signature(user, nonce)}",
        max_age=DEVICE_TTL,
        path=_PATH,
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
    )


def device_nonce(request: Request, user: User) -> str | None:
    """The nonce of a valid device cookie for *user* on *request*, if any."""
    nonce, _, signature = request.cookies.get(
        device_cookie_name(user.id), ""
    ).partition(".")
    if nonce and hmac.compare_digest(signature, _signature(user, nonce)):
        return nonce
    return None
