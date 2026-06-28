import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi_toolsets.exceptions import ForbiddenError, UnauthorizedError
from fastapi_multiauth import APIKeyCookieAuth, HTTPBearerAuth, MultiAuth
from redis.asyncio import Redis
from sqlalchemy.orm import selectinload

import nexctf.crud as crud
from nexctf.core.config import settings
from nexctf.core.db import get_db_context
from nexctf.model import User, UserRole, UserToken
from nexctf.schema import UserTokenCreate

TOKEN_PREFIX = "nexctf_"

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


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_single_use_token(
    redis: Redis, prefix: str, ttl: int, subject_id: UUID
) -> str:
    """Mint a single-use token and store its hash → subject id under ``prefix``.

    Only the token's hash is persisted (with a TTL); the raw token is returned to
    the caller to embed in a link. Shared by password-reset and email-verification.
    """
    token = secrets.token_urlsafe(32)
    await redis.setex(f"{prefix}{_hash_token(token)}", ttl, str(subject_id))
    return token


async def consume_single_use_token(redis: Redis, prefix: str, token: str) -> str | None:
    """Atomically consume a single-use token, returning its subject id or None.

    Uses GETDEL so the token is invalidated on first read, preventing double-use.
    """
    return await cast(Any, redis.getdel(f"{prefix}{_hash_token(token)}"))


async def _verify_token(token: str, role: UserRole | None = None) -> User:
    async with get_db_context() as db:
        user_token = await crud.UserTokenCrud.first(
            session=db,
            filters=[UserToken.token_hash == _hash_token(token)],
            load_options=[selectinload(UserToken.user)],
        )

        if user_token is None or not user_token.user.is_active:
            raise UnauthorizedError()

        if user_token.expires_at and user_token.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError()

        user = user_token.user

        if role is not None and user.role != role:
            raise ForbiddenError()

        return user


async def _verify_cookie(credential: str, role: UserRole | None = None) -> User:
    try:
        user_id_str, version_str = credential.split(":", 1)
        expected_version = int(version_str)
    except ValueError:
        raise UnauthorizedError()

    async with get_db_context() as db:
        user = await crud.UserCrud.first(
            session=db,
            filters=[User.id == UUID(user_id_str)],
        )

    if not user or not user.is_active:
        raise UnauthorizedError()

    if user.session_version != expected_version:
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
)
auth = MultiAuth(bearer_auth, cookie_auth)


async def create_api_token(
    user_id: UUID,
    *,
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
            ),
        )
    return raw, token_row
