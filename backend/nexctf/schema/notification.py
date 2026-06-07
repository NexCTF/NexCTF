from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminNotificationCreate(PydanticBase):
    title: str
    content: str
    is_broadcast: bool = False
    created_by_id: UUID
    team_ids: list[UUID] = []


class AdminNotificationUpdate(PydanticBase):
    id: UUID
    title: str | None = None
    content: str | None = None
    is_broadcast: bool | None = None


class AdminNotificationRead(PydanticBase):
    id: UUID
    title: str
    is_broadcast: bool
    created_by_id: UUID
    created_by_username: str | None = None
    created_at: datetime


class AdminNotificationReadDetail(AdminNotificationRead):
    content: str


class PublicNotificationItem(PydanticBase):
    id: UUID
    title: str
    content: str
    is_broadcast: bool
    created_at: datetime


class PublicNotificationListResponse(PydanticBase):
    notifications: list[PublicNotificationItem]
    last_read_at: datetime | None
