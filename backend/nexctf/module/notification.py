from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi_toolsets.schemas import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.exceptions import InternalServerError
from nexctf.schema.notification import (
    AdminNotificationCreate,
    AdminNotificationReadDetail,
)


async def publish_notification(
    redis: Redis,
    is_broadcast: bool,
    team_ids: list[UUID],
    notif_json: str,
) -> None:
    publishes = []
    if is_broadcast:
        publishes.append(redis.publish("notifications:broadcast", notif_json))
    for team_id in team_ids:
        publishes.append(redis.publish(f"notifications:team:{team_id}", notif_json))
    if publishes:
        await asyncio.gather(*publishes)


async def create_and_publish(
    session: AsyncSession,
    redis: Redis,
    obj: AdminNotificationCreate,
) -> Response[AdminNotificationReadDetail]:
    """Persist a notification and announce it on its team/broadcast channels."""
    response = await crud.NotificationCrud.create(
        session=session, obj=obj, schema=AdminNotificationReadDetail
    )
    if response.data is None:
        raise InternalServerError()
    await publish_notification(
        redis, obj.is_broadcast, obj.team_ids, response.data.model_dump_json()
    )
    return response
