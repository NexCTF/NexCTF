from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Security
from fastapi_toolsets.schemas import Response
from sqlalchemy import ColumnElement, or_, select

from nexctf.api.dep import RedisDep, SessionDep
from nexctf.api.security import auth
from nexctf.crud import NotificationCrud
from nexctf.model import Notification, User
from nexctf.model.notification import notification_team_table
from nexctf.schema.notification import (
    PublicNotificationItem,
    PublicNotificationListResponse,
)

notification_router = APIRouter(prefix="/notification", tags=["Notification"])


def _user_visibility_filter(user: User) -> ColumnElement[bool]:
    """SQLAlchemy filter: broadcast OR user's team is a target."""
    if user.team_id is not None:
        return or_(
            Notification.is_broadcast.is_(True),
            Notification.id.in_(
                select(notification_team_table.c.notification_id).where(
                    notification_team_table.c.team_id == user.team_id
                )
            ),
        )
    return Notification.is_broadcast.is_(True)


@notification_router.get("")
async def get_my_notifications(
    session: SessionDep,
    redis: RedisDep,
    user: User = Security(auth),
) -> Response[PublicNotificationListResponse]:
    rows = await NotificationCrud.get_multi(
        session=session,
        filters=[_user_visibility_filter(user)],
        order_by=Notification.created_at.desc(),
    )

    raw = await cast(Any, redis.get(f"notification:last_read:{user.id}"))
    last_read_at = datetime.fromisoformat(raw) if raw else None

    return Response(
        data=PublicNotificationListResponse(
            notifications=[PublicNotificationItem.model_validate(r) for r in rows],
            last_read_at=last_read_at,
        )
    )


@notification_router.post("/read", status_code=204)
async def mark_notifications_read(
    redis: RedisDep,
    user: User = Security(auth),
):
    """Record that the user has read all notifications up to now."""
    now = datetime.now(timezone.utc).isoformat()
    await redis.set(f"notification:last_read:{user.id}", now)
