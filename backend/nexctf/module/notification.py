from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.core.eventbus import publish_event
from nexctf.exceptions import InternalServerError
from nexctf.schema.notification import (
    AdminNotificationCreate,
    AdminNotificationReadDetail,
    PublicNotificationItem,
)


async def publish_notification(
    redis: Redis,
    is_broadcast: bool,
    team_ids: list[UUID],
    notif_json: str,
) -> None:
    channels = ["notifications:broadcast"] if is_broadcast else []
    channels += [f"notifications:team:{team_id}" for team_id in team_ids]
    await publish_event(redis, channels, notif_json)


async def create_notification(
    session: AsyncSession, obj: AdminNotificationCreate
) -> AdminNotificationReadDetail:
    """Persist a notification."""
    response = await crud.NotificationCrud.create(
        session=session, obj=obj, schema=AdminNotificationReadDetail
    )
    if response.data is None:
        raise InternalServerError()
    return response.data


async def announce_notification(
    redis: Redis,
    obj: AdminNotificationCreate,
    notification: AdminNotificationReadDetail,
) -> None:
    """Publish the public view of *notification* on its team or broadcast channels."""
    public = PublicNotificationItem.model_validate(notification, from_attributes=True)
    await publish_notification(
        redis, obj.is_broadcast, obj.team_ids, public.model_dump_json()
    )


async def create_and_publish(
    session: AsyncSession,
    redis: Redis,
    obj: AdminNotificationCreate,
) -> AdminNotificationReadDetail:
    """Persist a notification and announce it on its team/broadcast channels."""
    notification = await create_notification(session, obj)
    await announce_notification(redis, obj, notification)
    return notification
