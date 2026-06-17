from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import computed_field

from nexctf.module.events import category_for


class AdminEventRead(PydanticBase):
    id: UUID
    created_at: datetime
    event_type: str
    ip: str | None
    meta: dict[str, Any]
    actor_id: UUID | None
    actor_username: str | None
    target_type: str | None
    target_id: UUID | None
    target_label: str | None

    @computed_field
    @property
    def category(self) -> str:
        return category_for(self.event_type)
