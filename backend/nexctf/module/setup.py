"""First-run setup: the console token that lets the first admin sign up."""

import secrets
from typing import Any, cast

from fastapi_multiauth import hash_token
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.core.config import settings
from nexctf.core.db import get_db_context
from nexctf.exceptions import InvalidSetupTokenError, SetupCompletedError
from nexctf.model import User, UserRole
from nexctf.module.user import create_verified_user
from nexctf.schema.setup import SetupAdminCreate
from nexctf.schema.user import AdminUserCreate

SETUP_TOKEN_KEY = "setup:token"
SETUP_DONE_KEY = "setup:done"

_admin_seen = False


async def admin_exists(session: AsyncSession) -> bool:
    """Whether any admin account exists."""
    return await crud.UserCrud.exists(session, filters=[User.role == UserRole.admin])


async def setup_done(redis: Redis) -> bool:
    """Whether an admin was ever seen, shared through Redis and kept per process."""
    global _admin_seen
    if _admin_seen:
        return True
    if await redis.exists(SETUP_DONE_KEY):
        _admin_seen = True
        return True
    async with get_db_context() as session:
        found = await admin_exists(session)
    if found:
        await redis.set(SETUP_DONE_KEY, "1")
        _admin_seen = True
    return found


async def issue_setup_token(redis: Redis, *, replace: bool) -> str | None:
    """Store a new setup token's hash; None when one exists and not *replace*."""
    token = secrets.token_urlsafe(32)
    stored = await redis.set(SETUP_TOKEN_KEY, hash_token(token), nx=not replace)
    return token if stored else None


async def setup_token_matches(redis: Redis, token: str) -> bool:
    """Whether *token* is the current setup token."""
    stored: str | None = await cast(Any, redis.get(SETUP_TOKEN_KEY))
    return stored is not None and secrets.compare_digest(stored, hash_token(token))


async def consume_setup_token(redis: Redis) -> bool:
    """Delete the setup token, returning False when it was already gone."""
    return bool(await redis.delete(SETUP_TOKEN_KEY))


async def create_first_admin(
    session: AsyncSession, redis: Redis, body: SetupAdminCreate
) -> User:
    """Create the first admin when *body* carries the current setup token."""
    if await admin_exists(session):
        raise SetupCompletedError()
    if not await setup_token_matches(redis, body.token):
        raise InvalidSetupTokenError()
    user = await create_verified_user(
        session,
        redis,
        AdminUserCreate(**body.model_dump(exclude={"token"}), role=UserRole.admin),
    )
    if not await consume_setup_token(redis):
        raise InvalidSetupTokenError()
    return user


def setup_link(token: str) -> str:
    """The frontend page that creates the first admin with *token*."""
    return f"{settings.FRONTEND_HOST}/setup?token={token}"
