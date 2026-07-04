from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy import select

import nexctf.crud as crud
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.api.security import (
    PWD_RESET_KEY_PREFIX,
    PWD_RESET_TTL,
    issue_single_use_token,
)
from nexctf.util.ip import get_client_ip
from nexctf.model import CustomFieldValue, User
from nexctf.model.event import Event
from nexctf.module.events import emit
from nexctf.schema.custom_field import AdminCustomFieldValueRead
from nexctf.schema.event import AdminEventRead
from nexctf.schema.user import (
    AdminUserDetailRead,
    AdminUserUpdate,
    PublicUserRead,
    UserEmailVerifiedUpdate,
    UserTotpUpdate,
)

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
    login_row = (
        await session.execute(
            select(Event.ip, Event.created_at)
            .where(Event.actor_id == uuid, Event.event_type == "user.login")
            .order_by(Event.created_at.desc())
            .limit(1)
        )
    ).first()
    cfv_rows = await crud.CustomFieldValueCrud.get_multi(
        session=session, filters=[CustomFieldValue.user_id == uuid]
    )
    return Response(
        data=AdminUserDetailRead(
            **result.data.model_dump(),
            last_login_ip=login_row.ip if login_row else None,
            last_login_at=login_row.created_at if login_row else None,
            custom_field_values=[
                AdminCustomFieldValueRead.model_validate(cfv) for cfv in cfv_rows
            ],
        )
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
    result = await crud.UserCrud.update(
        session=session,
        filters=[User.id == uuid],
        obj=obj,
        schema=PublicUserRead,
    )
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
