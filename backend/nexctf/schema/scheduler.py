from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from nexctf.util.pydantic import InlineSelect, SelectOption


class TaskStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class SendNotificationParams(PydanticBase):
    title: str
    content: str
    is_broadcast: bool = False
    team_ids: list[UUID] = []


async def _get_challenge_options() -> list[SelectOption]:
    from sqlalchemy import select as sa_select
    from nexctf.core.db import get_db_context
    from nexctf.model.challenge import Challenge

    async with get_db_context() as session:
        rows = await session.execute(
            sa_select(Challenge.id, Challenge.title).order_by(Challenge.title)
        )
        return [SelectOption(value=str(r.id), label=r.title) for r in rows]


class ToggleChallengeParams(PydanticBase):
    challenge_id: Annotated[UUID, InlineSelect(_get_challenge_options)]
    make_active: bool


class AdminSchedulerJobCreate(PydanticBase):
    name: str
    job_type: str
    scheduled_at: datetime
    is_active: bool = True
    params: dict


class AdminSchedulerJobCreateInternal(AdminSchedulerJobCreate):
    created_by_id: UUID


class AdminSchedulerJobUpdate(PydanticBase):
    name: str | None = None
    scheduled_at: datetime | None = None
    is_active: bool | None = None
    params: dict | None = None


class AdminSchedulerTaskRead(PydanticBase):
    id: UUID
    job_id: UUID
    status: TaskStatus
    started_at: datetime
    completed_at: datetime | None
    error: str | None
    created_at: datetime


class AdminSchedulerJobRead(PydanticBase):
    id: UUID
    name: str
    job_type: str
    is_active: bool
    scheduled_at: datetime
    params: dict
    last_run: datetime | None
    created_at: datetime
    created_by_id: UUID


class AdminSchedulerJobReadDetail(AdminSchedulerJobRead):
    tasks: list[AdminSchedulerTaskRead] = []


class AdminSchedulerJobTypeRead(PydanticBase):
    type_name: str
    create_schema: dict
    update_schema: dict
