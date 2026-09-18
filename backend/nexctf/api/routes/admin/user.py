from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

from nexctf import crud
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.api.security import (
    PWD_RESET_KEY_PREFIX,
    PWD_RESET_TTL,
    current_sid_hash,
    hash_password,
    issue_single_use_token,
)
from nexctf.model import CustomFieldValue, User
from nexctf.model.event import Event
from nexctf.module.custom_field import replace_custom_field_values
from nexctf.module.events import emit
from nexctf.module.session import (
    account_origin,
    live_sessions,
    revoke_session_by_id,
)
from nexctf.schema.custom_field import AdminCustomFieldValueRead
from nexctf.schema.event import AdminEventRead
from nexctf.schema.user import (
    AdminUserCreate,
    AdminUserDetailRead,
    AdminUserUpdate,
    PublicUserRead,
    UserCreate,
    UserEmailVerifiedUpdate,
    UserSessionRead,
    UserTotpUpdate,
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
) -> Response[PublicUserRead]:
    """Create a user directly, bypassing registration gating and email verification."""
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
    uuid: UUID,
) -> Response[AdminUserDetailRead]:
    result = await crud.UserCrud.get(
        session=session,
        filters=[User.id == uuid],
        schema=PublicUserRead,
    )
    if result.data is None:
        raise NotFoundError()
    origin = await account_origin(session, uuid)
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
            for row in await live_sessions(session, uuid)
        ]
    )


@user_router.delete("/{uuid}/sessions/{session_id}", status_code=204)
async def revoke_user_session(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
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
    uuid: UUID,
    obj: AdminUserUpdate,
    admin: CurrentUserDep,
) -> Response[PublicUserRead]:
    if obj.email is not None:
        # Changing the address invalidates any prior verification of it.
        target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
        if target and obj.email != target.email:
            await crud.UserCrud.update(
                session=session,
                filters=[User.id == uuid],
                obj=UserEmailVerifiedUpdate(id=uuid, email_verified=False),
            )
    try:
        result = await crud.UserCrud.update(
            session=session,
            filters=[User.id == uuid],
            obj=obj,
            schema=PublicUserRead,
        )
    except IntegrityError:
        raise ConflictError(detail="Username or email already taken")
    changes = obj.model_dump(exclude={"id"}, exclude_unset=True)
    await emit(
        session,
        redis,
        event_type="admin.user_updated",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={"target_user_id": str(uuid), **{k: str(v) for k, v in changes.items()}},
    )
    return result


@user_router.post("/{uuid}/totp/reset", status_code=204)
async def admin_reset_totp(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    admin: CurrentUserDep,
):
    """Clear TOTP for a user (admin action, no OTP code required)."""
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    if not target:
        raise NotFoundError()
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == uuid],
        obj=UserTotpUpdate(id=uuid, totp_secret=None),
    )
    await emit(
        session,
        redis,
        event_type="admin.user_totp_reset",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={"target_user_id": str(uuid), "target_username": target.username},
    )


@user_router.post("/{uuid}/password-reset-token")
async def admin_create_password_reset_token(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    admin: CurrentUserDep,
) -> Response[str]:
    """Generate a single-use password reset token for a user (valid 1 hour)."""
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    if not target:
        raise NotFoundError()
    token = await issue_single_use_token(
        redis, PWD_RESET_KEY_PREFIX, PWD_RESET_TTL, uuid
    )
    await emit(
        session,
        redis,
        event_type="admin.user_password_reset_token",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={"target_user_id": str(uuid), "target_username": target.username},
    )
    return Response(data=token)


@user_router.delete("/{uuid}")
async def delete_user(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    admin: CurrentUserDep,
) -> Response[None]:
    target = await crud.UserCrud.first(session=session, filters=[User.id == uuid])
    result = await crud.UserCrud.delete(
        session=session, filters=[User.id == uuid], return_response=True
    )
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
