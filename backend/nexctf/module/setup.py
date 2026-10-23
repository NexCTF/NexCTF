"""First-run setup: the console token that lets the first admin sign up."""

import secrets
from typing import Any, cast

from fastapi_multiauth import hash_token
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.core.config import settings
from nexctf.exceptions import InvalidSetupTokenError, SetupCompletedError
from nexctf.model import User, UserRole
from nexctf.module.user import create_verified_user
from nexctf.schema.setup import SetupAdminCreate
from nexctf.schema.user import AdminUserCreate

SETUP_TOKEN_KEY = "setup:token"

_admin_seen = False


async def admin_exists(session: AsyncSession) -> bool:
    """Whether any admin account exists."""
    return await crud.UserCrud.exists(session, filters=[User.role == UserRole.admin])


async def setup_done(session: AsyncSession) -> bool:
    """Whether an admin exists, remembered by this process once one has been seen."""
    global _admin_seen
    _admin_seen = _admin_seen or await admin_exists(session)
    return _admin_seen


async def issue_setup_token(redis: Redis) -> str:
    """Store a new setup token's hash, replacing any previous one."""
    token = secrets.token_urlsafe(32)
    await redis.set(SETUP_TOKEN_KEY, hash_token(token))
    return token


async def setup_token_matches(redis: Redis, token: str) -> bool:
    """Whether *token* is the current setup token."""
    stored: str | None = await cast(Any, redis.get(SETUP_TOKEN_KEY))
    return stored is not None and secrets.compare_digest(stored, hash_token(token))


async def consume_setup_token(redis: Redis) -> bool:
    """Delete the setup token, returning False when it was already gone."""
    return bool(await redis.delete(SETUP_TOKEN_KEY))


async def refresh_setup_token(session: AsyncSession, redis: Redis) -> str | None:
    """Issue a new setup token while no admin exists, else drop it."""
    if await admin_exists(session):
        await consume_setup_token(redis)
        return None
    return await issue_setup_token(redis)


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
