from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import AfterValidator, Field, model_validator

from nexctf.util.cron import validate_cron
from nexctf.util.pydantic import InlineSelect, SelectOption

CronExpression = Annotated[str, Field(max_length=128), AfterValidator(validate_cron)]


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
    from sqlalchemy import select

    from nexctf.core.db import get_db_context
    from nexctf.model.challenge import Challenge

    async with get_db_context() as session:
        rows = await session.execute(
            select(Challenge.id, Challenge.title).order_by(Challenge.title)
        )
        return [SelectOption(value=str(r.id), label=r.title) for r in rows]


class ToggleChallengeParams(PydanticBase):
    challenge_id: Annotated[UUID, InlineSelect(_get_challenge_options)]
    make_active: bool


class AdminSchedulerJobCreate(PydanticBase):
    name: str
    job_type: str
    scheduled_at: datetime | None = None
    cron_expression: CronExpression | None = None
    is_active: bool = True
    params: dict

    @model_validator(mode="after")
    def _require_a_schedule(self) -> Self:
        """A job fires either at a fixed time, on a cron, or it is not a job."""
        if self.scheduled_at is None and self.cron_expression is None:
            raise ValueError("scheduled_at is required without a cron_expression")
        return self


class AdminSchedulerJobCreateInternal(AdminSchedulerJobCreate):
    scheduled_at: datetime
    created_by_id: UUID


class AdminSchedulerJobUpdate(PydanticBase):
    name: str | None = None
    scheduled_at: datetime | None = None
    cron_expression: CronExpression | None = None
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
    cron_expression: str | None
    params: dict
    last_run: datetime | None
    created_at: datetime
    created_by_id: UUID


class AdminSchedulerJobTypeRead(PydanticBase):
    type_name: str
    create_schema: dict
    update_schema: dict


class CronPreview(PydanticBase):
    timezone: str
    next_runs: list[datetime]
