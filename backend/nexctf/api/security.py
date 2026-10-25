import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Request, Response
from fastapi_multiauth import (
    APIKeyCookieAuth,
    HTTPBearerAuth,
    MultiAuth,
    StaleCredentialError,
)
from fastapi_toolsets.exceptions import ForbiddenError, UnauthorizedError
from redis.asyncio import Redis
from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.api.scope import (
    bind_token,
    token_id_of,
    token_name_of,
    with_implied_reads,
)
from nexctf.core import appconfig
from nexctf.core.cache import get_client
from nexctf.core.config import settings
from nexctf.core.db import get_auth_db_context, get_db_context
from nexctf.model import User, UserRole, UserToken
from nexctf.module.client import ClientInfo
from nexctf.module.session import (
    SESSION_TTL,
    rotate_session,
    session_idle,
    start_session,
    touch_live_session,
)
from nexctf.schema import UserTokenCreate

TOKEN_PREFIX = "nexctf_"
LAST_USED_THROTTLE = timedelta(minutes=5)
REAUTH_WINDOW = 600  # 10 minutes

_ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


# Precomputed hash of a throwaway password. Verifying against it lets login
# spend the same Argon2 cost when the account is missing or has no password as
# when it exists, so response timing does not reveal which usernames are valid.
_DUMMY_PASSWORD_HASH = _ph.hash("nexctf-dummy-password")


def dummy_verify_password(plain: str) -> None:
    """Run a throwaway verification to match the cost of a real password check."""
    verify_password(plain, _DUMMY_PASSWORD_HASH)


PWD_RESET_KEY_PREFIX = "pwd_reset:"
PWD_RESET_TTL = 3600  # 1 hour
EMAIL_VERIFY_KEY_PREFIX = "email_verify:"
EMAIL_VERIFY_TTL = 86400  # 24 hours
TOTP_USED_KEY_PREFIX = "totp:used:"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_single_use_token(
    redis: Redis, prefix: str, ttl: int, subject: str
) -> str:
    """Mint a single-use token and store its hash → subject under ``prefix``.

    Only the token's hash is persisted (with a TTL); the raw token is returned to
    the caller to embed in a link. Shared by password-reset, email-verification
    and backup downloads.
    """
    token = secrets.token_urlsafe(32)
    await redis.set(f"{prefix}{_hash_token(token)}", subject, ex=ttl)
    return token


async def issue_password_reset_token(redis: Redis, user: User) -> str:
    """Mint a reset token that stops working once the user's password changes."""
    return await issue_single_use_token(
        redis, PWD_RESET_KEY_PREFIX, PWD_RESET_TTL, f"{user.id}:{user.session_version}"
    )


async def consume_single_use_token(redis: Redis, prefix: str, token: str) -> str | None:
    """Atomically consume a single-use token, returning its subject or None.

    Uses GETDEL so the token is invalidated on first read, preventing double-use.
    """
    return await cast(Any, redis.getdel(f"{prefix}{_hash_token(token)}"))


async def consume_password_reset_token(
    redis: Redis, token: str
) -> tuple[UUID, int] | None:
    """Consume a reset token, returning its user id and session version, or None."""
    subject = await consume_single_use_token(redis, PWD_RESET_KEY_PREFIX, token)
    user_id, _, session_version = (subject or "").partition(":")
    if not session_version.isdigit():
        return None
    return UUID(user_id), int(session_version)


async def verify_totp_once(redis: Redis, user_id: UUID, secret: str, code: str) -> bool:
    """Check a TOTP code within one step of drift, refusing one already used."""
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return False
    key = f"{TOTP_USED_KEY_PREFIX}{user_id}:{code}"
    return bool(await redis.set(key, "1", nx=True, ex=totp.interval * 3))


async def _verify_token(
    token: str, role: UserRole | None = None, request: Request | None = None
) -> User:
    """Resolve an API token to its user, binding the token's scopes to *request*."""
    if request is None:
        raise UnauthorizedError()

    async with get_auth_db_context() as db:
        user_token = await crud.UserTokenCrud.first(
            session=db,
            filters=[UserToken.token_hash == _hash_token(token)],
            load_options=[selectinload(UserToken.user).selectinload(User.team)],
        )

        if user_token is None or not user_token.user.is_active:
            raise UnauthorizedError()

        now = datetime.now(UTC)
        if user_token.expires_at and user_token.expires_at < now:
            raise UnauthorizedError()

        user = user_token.user

        if role is not None and user.role != role:
            raise ForbiddenError()

        await db.execute(
            update(UserToken)
            .where(
                UserToken.id == user_token.id,
                or_(
                    UserToken.last_used_at.is_(None),
                    UserToken.last_used_at <= now - LAST_USED_THROTTLE,
                ),
            )
            .values(last_used_at=now)
        )

        bind_token(request, user_token.id, user_token.name, user_token.scopes)
        return user


async def request_overrides(request: Request, redis: Redis) -> dict[str, str]:
    """The config overrides snapshot for *request*, fetched once and then reused."""
    cached = getattr(request.state, "config_overrides", None)
    if cached is None:
        cached = request.state.config_overrides = await appconfig.fetch_overrides(redis)
    return cached


async def _verify_cookie(
    credential: str,
    *,
    session_id: str,
    role: UserRole | None = None,
    request: Request | None = None,
) -> User:
    if request is None:
        raise UnauthorizedError()
    try:
        user_id_str, version_str = credential.split(":", 1)
        expected_version = int(version_str)
        user_id = UUID(user_id_str)
    except ValueError:
        raise UnauthorizedError()

    idle = session_idle(await request_overrides(request, get_client()))
    async with get_auth_db_context() as db:
        user = await crud.UserCrud.first(session=db, filters=[User.id == user_id])

        if not user or not user.is_active:
            raise UnauthorizedError()

        if user.session_version != expected_version:
            raise UnauthorizedError()

        if not await touch_live_session(db, session_id, user_id, idle):
            raise UnauthorizedError()

    if role is not None and user.role != role:
        raise ForbiddenError()

    return user


bearer_auth = HTTPBearerAuth(
    validator=_verify_token,
    prefix=TOKEN_PREFIX,
)
cookie_auth = APIKeyCookieAuth(
    name="NexCTF",
    validator=_verify_cookie,
    secret_key=settings.SECRET_KEY,
    secure=settings.ENVIRONMENT != "development",
    ttl=SESSION_TTL,
    session_id=True,
    csrf=True,
    trusted_origins=settings.all_cors_origins,
)
auth = MultiAuth(bearer_auth, cookie_auth)


def client_of(request: Request) -> ClientInfo:
    """The client behind an authenticated *request*."""
    return ClientInfo.build(
        request.headers.get("user-agent"), token_id_of(request), token_name_of(request)
    )


def current_sid_hash(request: Request) -> str | None:
    """Hash of the cookie session id on *request*, to match against stored sessions."""
    sid = cookie_auth.session_id_of(request)
    return _hash_token(sid) if sid else None


def require_fresh_cookie(request: Request) -> None:
    """Refuse a session cookie signed longer ago than the re-authentication window."""
    signed_at = cookie_auth.authenticated_at(request.cookies.get(cookie_auth.name, ""))
    if signed_at is None or not 0 <= time.time() - signed_at <= REAUTH_WINDOW:
        raise StaleCredentialError(max_age=REAUTH_WINDOW)


def _set_session_cookie(response: Response, user: User) -> str:
    """Set a newly signed session cookie for *user*, returning its session id."""
    sid = cookie_auth.set_cookie(response, f"{user.id}:{user.session_version}")
    if sid is None:  # session_id=True always mints one
        raise RuntimeError("cookie_auth must be built with session_id=True")
    return sid


async def issue_session_cookie(
    db: AsyncSession, response: Response, user: User, request: Request
) -> None:
    """Sign the user in on this device: set the cookie and record its session."""
    sid = _set_session_cookie(response, user)
    await start_session(db, sid, user=user, request=request)


async def reissue_session_cookie(
    db: AsyncSession, response: Response, user: User, request: Request
) -> None:
    """Re-sign this device's cookie in place, keeping its session row and expiry."""
    old_sid = cookie_auth.session_id_of(request)
    if old_sid is None:
        raise UnauthorizedError()
    if not await rotate_session(db, old_sid, _set_session_cookie(response, user)):
        raise UnauthorizedError()


async def create_api_token(
    user_id: UUID,
    *,
    scopes: list[str],
    name: str | None = None,
    expires_at: datetime | None = None,
) -> tuple[str, UserToken]:
    raw = bearer_auth.generate_token()
    async with get_db_context() as db:
        token_row = await crud.UserTokenCrud.create(
            session=db,
            obj=UserTokenCreate(
                user_id=user_id,
                token_hash=_hash_token(raw),
                name=name,
                expires_at=expires_at,
                scopes=with_implied_reads(scopes),
            ),
        )
    return raw, token_row
