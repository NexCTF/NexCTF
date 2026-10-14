from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

from nexctf import crud
from nexctf.api.dep import RedisDep, SessionDep
from nexctf.model import Notification
from nexctf.module import notification as notifications
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
    background_tasks: BackgroundTasks,
) -> Response[AdminNotificationReadDetail]:
    """Create a notification, announced to players once it is committed."""
    notification = await notifications.create_notification(session, obj)
    background_tasks.add_task(
        notifications.announce_notification, redis, obj, notification
    )
    return Response(data=notification)


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
