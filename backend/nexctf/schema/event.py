from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminEventRead(PydanticBase):
    id: UUID
    created_at: datetime
    event_type: str
    ip: str | None
    meta: dict[str, Any]
    actor_id: UUID | None
    actor_username: str | None
    team_id: UUID | None
    team_name: str | None
    challenge_id: UUID | None
    challenge_title: str | None
