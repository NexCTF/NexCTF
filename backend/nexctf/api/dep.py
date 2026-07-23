from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request, Security
from fastapi_toolsets.dependencies import PathDependency
from fastapi_toolsets.exceptions import NotFoundError
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.security import auth, bearer_auth, cookie_auth
from nexctf.core import appconfig
from nexctf.core.cache import get_redis
from nexctf.core.db import db
from nexctf.exceptions import EventEndedError, EventNotStartedError, NoTeamError
from nexctf.model import Challenge, OAuthProvider, Solution, User, UserRole
from nexctf.module.audit import AuditContext, set_audit_context
from nexctf.plugins.registry import (
    challenge_registry,
    solution_registry,
)
from nexctf.util.datetime import is_config_dt_past, parse_config_dt
from nexctf.util.ip import get_client_ip

SessionDep = Annotated[AsyncSession, Depends(db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
CurrentUserDep = Annotated[User, Security(auth)]

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def invalidate_on_write(
    *invalidators: Callable[[Redis], Awaitable[None]],
) -> Callable[[Request, Redis], AsyncGenerator[None, None]]:
    """Build a router dependency that invalidates caches after a mutating request.

    The returned dependency lets the endpoint run, then runs every invalidator
    for write methods (POST/PUT/PATCH/DELETE). It deliberately runs even when the
    endpoint failed: over-invalidating only forces a harmless recompute, whereas
    skipping invalidation would serve stale data.

    Args:
        invalidators: Async callables taking a Redis client and clearing a cache.
    """

    async def _dep(request: Request, redis: RedisDep) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            if request.method in _WRITE_METHODS:
                for invalidate in invalidators:
                    await invalidate(redis)

    return _dep


async def bind_audit_context(request: Request, user: CurrentUserDep) -> None:
    """Bind the acting user and client IP for audit logging on this request."""
    set_audit_context(AuditContext(actor_id=user.id, ip=get_client_ip(request)))


async def _optional_auth(request: Request) -> User | None:
    """Try bearer then cookie; return None if neither succeeds."""
    for source in (bearer_auth, cookie_auth):
        credential = await source.extract(request)
        if credential is not None:
            try:
                return await source.authenticate(credential)
            except Exception:
                return None
    return None


OptionalCurrentUserDep = Annotated[User | None, Depends(_optional_auth)]


_STAFF = (UserRole.admin, UserRole.moderator)


def _is_staff(user: User | None) -> bool:
    return user is not None and user.role in _STAFF


async def _event_started(user: OptionalCurrentUserDep = None) -> None:
    """Raise EventNotStartedError before the CTF starts. Admins/mods bypass."""
    if _is_staff(user):
        return
    if not bool(appconfig.get("ctf.hide_challenges_before_start")):
        return
    start_time = parse_config_dt("ctf.start_time")
    if start_time is not None and datetime.now(timezone.utc) < start_time:
        raise EventNotStartedError()


async def _event_ended(user: OptionalCurrentUserDep = None) -> None:
    """Raise EventEndedError after the CTF ends. Admins/mods bypass."""
    if _is_staff(user):
        return
    if is_config_dt_past("ctf.end_time"):
        raise EventEndedError()


async def _event_active(user: OptionalCurrentUserDep = None) -> None:
    """Raise if the CTF has not started or has already ended. Admins/mods bypass."""
    await _event_started(user)
    await _event_ended(user)


EventStartedDep = Annotated[None, Depends(_event_started)]
EventEndedDep = Annotated[None, Depends(_event_ended)]
EventActiveDep = Annotated[None, Depends(_event_active)]


async def _require_team(user: CurrentUserDep) -> User:
    """Raise NoTeamError if the authenticated user has no team."""
    if user.team_id is None:
        raise NoTeamError()
    return user


RequireTeamDep = Annotated[User, Depends(_require_team)]

ProviderDep = PathDependency(
    model=OAuthProvider,
    field=OAuthProvider.slug,
    session_dep=db,
    param_name="slug",
)

type PolyCtx = tuple[Any, type[BaseModel], type[BaseModel]]
type SolutionCtx = tuple[Any, type[BaseModel], type[BaseModel], UUID | None]


async def validate_body(schema: type[BaseModel], request: Request) -> BaseModel:
    return schema.model_validate(await request.json())


async def challenge_create_dep(challenge_type: str, request: Request) -> BaseModel:
    try:
        entry = challenge_registry.get(challenge_type)
    except KeyError:
        raise NotFoundError(detail=f"Unknown challenge type: {challenge_type!r}")
    return await validate_body(entry.create_schema, request)


async def challenge_ctx_dep(uuid: UUID, session: SessionDep) -> PolyCtx:
    row = await session.execute(
        select(Challenge.challenge_type).where(Challenge.id == uuid)
    )
    challenge_type = row.scalar_one_or_none()
    if challenge_type is None:
        raise NotFoundError()
    try:
        entry = challenge_registry.get(challenge_type)
    except KeyError:
        raise NotFoundError(detail=f"Unregistered challenge type: {challenge_type!r}")
    return entry.crud, entry.update_schema, entry.read_schema


ChallengeCreateDep = Annotated[BaseModel, Depends(challenge_create_dep)]
ChallengeCtxDep = Annotated[PolyCtx, Depends(challenge_ctx_dep)]


async def solution_create_dep(solve_type: str, request: Request) -> BaseModel:
    try:
        entry = solution_registry.get(solve_type)
    except KeyError:
        raise NotFoundError(detail=f"Unknown solution type: {solve_type!r}")
    return await validate_body(entry.create_schema, request)


async def solution_ctx_dep(uuid: UUID, session: SessionDep) -> SolutionCtx:
    row = await session.execute(
        select(Solution.solve_type, Solution.question_id).where(Solution.id == uuid)
    )
    result = row.one_or_none()
    if result is None:
        raise NotFoundError()
    solve_type, question_id = result
    try:
        entry = solution_registry.get(solve_type)
    except KeyError:
        raise NotFoundError(detail=f"Unregistered solution type: {solve_type!r}")
    return entry.crud, entry.update_schema, entry.read_schema, question_id


SolutionCreateDep = Annotated[BaseModel, Depends(solution_create_dep)]
SolutionCtxDep = Annotated[SolutionCtx, Depends(solution_ctx_dep)]
