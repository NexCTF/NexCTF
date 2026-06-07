from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.exceptions import InternalServerError
from nexctf.api.dep import RedisDep, SessionDep
from nexctf.model import Notification
from nexctf.module.notification import publish_notification
from nexctf.schema.notification import (
    AdminNotificationCreate,
    AdminNotificationRead,
    AdminNotificationReadDetail,
    AdminNotificationUpdate,
)

notification_router = APIRouter(prefix="/notification", tags=["Notification"])


@notification_router.get("")
async def get_notifications(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.NotificationCrud.paginate_params())],
) -> PaginatedResponse[AdminNotificationRead]:
    return await crud.NotificationCrud.paginate(
        session=session,
        **params,
        schema=AdminNotificationRead,
    )


@notification_router.post("")
async def create_notification(
    session: SessionDep,
    redis: RedisDep,
    obj: AdminNotificationCreate,
) -> Response[AdminNotificationReadDetail]:
    response = await crud.NotificationCrud.create(
        session=session, obj=obj, schema=AdminNotificationReadDetail
    )
    if response.data is None:
        raise InternalServerError()
    await publish_notification(
        redis, obj.is_broadcast, obj.team_ids, response.data.model_dump_json()
    )
    return response


@notification_router.get("/{uuid}")
async def get_notification(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminNotificationReadDetail]:
    return await crud.NotificationCrud.get(
        session=session,
        filters=[Notification.id == uuid],
        schema=AdminNotificationReadDetail,
    )


@notification_router.put("/{uuid}")
async def update_notification(
    session: SessionDep,
    uuid: UUID,
    obj: AdminNotificationUpdate,
) -> Response[AdminNotificationReadDetail]:
    return await crud.NotificationCrud.update(
        session=session,
        filters=[Notification.id == uuid],
        obj=obj,
        schema=AdminNotificationReadDetail,
    )


@notification_router.delete("/{uuid}")
async def delete_notification(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.NotificationCrud.delete(
        session=session,
        filters=[Notification.id == uuid],
        return_response=True,
    )
