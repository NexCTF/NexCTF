from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

from nexctf import crud
from nexctf.api.dep import (
    ClientCategoryDep,
    CurrentUserDep,
    FreshAuthDep,
    FreshSessionDep,
    RedisDep,
    SessionDep,
    SessionIdleDep,
    TokenScopesDep,
    require_fresh_session,
    require_fresh_unless_token,
)
from nexctf.api.security import (
    current_sid_hash,
    hash_password,
    issue_password_reset_token,
)
from nexctf.core.eventbus import close_user_streams
from nexctf.model import CustomFieldValue, User, UserRole
from nexctf.model.event import Event
from nexctf.module.client import user_clients
from nexctf.module.custom_field import replace_custom_field_values
from nexctf.module.events import emit
from nexctf.module.session import (
    account_origin,
    live_sessions,
    revoke_session_by_id,
    revoke_user_sessions,
)
from nexctf.module.user import reset_totp
from nexctf.schema.custom_field import AdminCustomFieldValueRead
from nexctf.schema.event import AdminEventRead
from nexctf.schema.user import (
    AdminUserClientRead,
    AdminUserCreate,
    AdminUserDetailRead,
    AdminUserUpdate,
    AdminUserUpdateRead,
    AdminUserUpdateRequest,
    PublicUserRead,
    UserCreate,
    UserEmailVerifiedUpdate,
    UserSessionRead,
)
from nexctf.util.ip import get_client_ip

user_router = APIRouter(prefix="/user", tags=["User"])


@user_router.get("")
async def get_users(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.UserCrud.paginate_params())],
) -> PaginatedResponse[PublicUserRead]:
    return await crud.UserCrud.paginate(
        session=session,
        **params,
        schema=PublicUserRead,
    )


@user_router.post("", status_code=201)
async def create_user(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    obj: AdminUserCreate,
    admin: CurrentUserDep,
    granted: TokenScopesDep,
) -> Response[PublicUserRead]:
    """Create a user directly, bypassing registration gating and email verification.

    Creating an admin needs a recently signed-in browser session.
    """
    if obj.role is UserRole.admin:
        require_fresh_session(request, granted)
    try:
        result = await crud.UserCrud.create(
            session=session,
            obj=UserCreate(
                username=obj.username,
                email=obj.email,
                hashed_password=hash_password(obj.password),
                email_verified=True,
                role=obj.role,
                team_id=obj.team_id,
            ),
            schema=PublicUserRead,
        )
    except IntegrityError:
        raise ConflictError(detail="Username or email already taken")
    if result.data is not None:
        await replace_custom_field_values(
            session, obj.custom_fields, user_id=result.data.id, self_service=False
        )
        await emit(
            session,
            redis,
            event_type="admin.user_created",
            actor_id=admin.id,
            ip=get_client_ip(request),
            meta={
                "target_user_id": str(result.data.id),
                "target_username": result.data.username,
            },
        )
    return result


@user_router.get("/{uuid}")
async def get_user(
    session: SessionDep,
    idle: SessionIdleDep,
    uuid: UUID,
) -> Response[AdminUserDetailRead]:
    result = await crud.UserCrud.get(
        session=session,
        filters=[User.id == uuid],
        schema=PublicUserRead,
    )
    if result.data is None:
        raise NotFoundError()
    origin = await account_origin(session, uuid, idle)
    cfv_rows = await crud.CustomFieldValueCrud.get_multi(
        session=session, filters=[CustomFieldValue.user_id == uuid]
    )
    return Response(
        data=AdminUserDetailRead(
            **result.data.model_dump(),
            ips=origin.addresses,
            last_login_at=origin.last_login_at,
            custom_field_values=[
                AdminCustomFieldValueRead.model_validate(cfv) for cfv in cfv_rows
            ],
        )
    )


@user_router.get("/{uuid}/sessions")
async def get_user_sessions(
    request: Request,
    session: SessionDep,
    idle: SessionIdleDep,
    uuid: UUID,
) -> Response[list[UserSessionRead]]:
    """A user's live sessions, most recently active first."""
    this_hash = current_sid_hash(request)
    return Response(
        data=[
            UserSessionRead(
                id=row.id,
                ip=row.ip,
                last_ip=row.last_ip,
                user_agent=row.user_agent,
                last_seen_at=row.last_seen_at,
                current=row.sid_hash == this_hash,
            )
            for row in await live_sessions(session, uuid, idle)
        ]
    )


@user_router.get("/{uuid}/clients")
async def get_user_clients(
    session: SessionDep,
    category: ClientCategoryDep,
    uuid: UUID,
) -> Response[list[AdminUserClientRead]]:
    """Every user-agent a user was seen with, most recently active first."""
    return Response(data=await user_clients(session, uuid, category))


@user_router.delete("/{uuid}/sessions/{session_id}", status_code=204)
async def revoke_user_session(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    uuid: UUID,
    session_id: UUID,
    admin: CurrentUserDep,
):
    """Sign one of a user's devices out."""
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    if not target:
        raise NotFoundError()
    if not await revoke_session_by_id(session, session_id, uuid):
        raise NotFoundError(detail="Session not found")
    background_tasks.add_task(close_user_streams, redis, uuid)
    await emit(
        session,
        redis,
        event_type="admin.user_session_revoked",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={"target_user_id": str(uuid), "target_username": target.username},
    )


@user_router.get("/{uuid}/events")
async def get_user_events(
    session: SessionDep,
    uuid: UUID,
    params: Annotated[dict, Depends(crud.EventCrud.paginate_params())],
) -> PaginatedResponse[AdminEventRead]:
    return await crud.EventCrud.paginate(
        session=session,
        **params,
        schema=AdminEventRead,
        filters=[Event.actor_id == uuid],
    )


@user_router.put("/{uuid}")
async def update_user(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    uuid: UUID,
    obj: AdminUserUpdateRequest,
    admin: CurrentUserDep,
    granted: TokenScopesDep,
) -> Response[AdminUserUpdateRead]:
    """Update a user; granting admin signs them out everywhere.

    Granting admin or changing an email needs a fresh session; demoting or
    deactivating an admin needs one unless called with an API token.
    """
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    email_changed = (
        target is not None and obj.email is not None and obj.email != target.email
    )
    granting_admin = obj.role is UserRole.admin and (
        target is None or target.role is not UserRole.admin
    )
    disarming_admin = (
        target is not None
        and target.role is UserRole.admin
        and (obj.role not in (None, UserRole.admin) or obj.is_active is False)
    )
    if email_changed or granting_admin:
        require_fresh_session(request, granted)
    elif disarming_admin:
        require_fresh_unless_token(request, granted)
    if target is None:
        raise NotFoundError()
    if email_changed:
        # Changing the address invalidates any prior verification of it.
        await crud.UserCrud.update(
            session=session,
            filters=[User.id == uuid],
            obj=UserEmailVerifiedUpdate(id=uuid, email_verified=False),
        )
    fields = obj.model_dump(exclude={"custom_fields"}, exclude_unset=True)
    access_changed = any(
        key in fields and fields[key] != getattr(target, key)
        for key in ("role", "is_active", "team_id")
    )
    try:
        result = await crud.UserCrud.update(
            session=session,
            filters=[User.id == uuid],
            obj=AdminUserUpdate(**fields),
            schema=AdminUserUpdateRead,
        )
    except IntegrityError:
        raise ConflictError(detail="Username or email already taken")
    if obj.custom_fields is not None:
        await replace_custom_field_values(
            session, obj.custom_fields, user_id=uuid, self_service=False
        )
    changes = {k: str(v) for k, v in fields.items() if k != "id"}
    meta = {"target_user_id": str(uuid), **changes}
    if granting_admin:
        await revoke_user_sessions(session, target)
        meta["sessions_revoked"] = "true"
    if access_changed:
        background_tasks.add_task(close_user_streams, redis, uuid)
    await emit(
        session,
        redis,
        event_type="admin.user_updated",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta=meta,
    )
    if result.data is not None:
        result.data.sessions_revoked = granting_admin
    return result


@user_router.post("/{uuid}/totp/reset", status_code=204)
async def admin_reset_totp(
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    admin: FreshSessionDep,
):
    """Clear TOTP for a user (admin action, no OTP code required)."""
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    if not target:
        raise NotFoundError()
    await reset_totp(session, redis, target)


@user_router.post("/{uuid}/password-reset-token")
async def admin_create_password_reset_token(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    admin: FreshSessionDep,
) -> Response[str]:
    """Generate a single-use password reset token for a user (valid 1 hour)."""
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    if not target:
        raise NotFoundError()
    token = await issue_password_reset_token(redis, target)
    await emit(
        session,
        redis,
        event_type="admin.user_password_reset_token",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={"target_user_id": str(uuid), "target_username": target.username},
    )
    return Response(data=token)


@user_router.delete("/{uuid}", dependencies=[FreshAuthDep])
async def delete_user(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    uuid: UUID,
    admin: CurrentUserDep,
) -> Response[None]:
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    result = await crud.UserCrud.delete(
        session=session, filters=[User.id == uuid], return_response=True
    )
    background_tasks.add_task(close_user_streams, redis, uuid)
    await emit(
        session,
        redis,
        event_type="admin.user_deleted",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={
            "target_user_id": str(uuid),
            "target_username": target.username if target else None,
        },
    )
    return result
