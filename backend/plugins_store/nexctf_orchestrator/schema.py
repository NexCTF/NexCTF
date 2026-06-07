from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi_toolsets.schemas import BaseModel
from nexctf.schema.challenge import (
    AdminChallengeCreate,
    AdminChallengeRead,
    AdminChallengeUpdate,
)
from nexctf.util.pydantic import InlineSelect, SelectOption
from pydantic import Field


async def _orchestrator_options() -> list[SelectOption]:
    """Return available orchestrators. Replace with a real lookup when ready."""
    return [
        SelectOption(
            value="4d165da4-40ed-473c-8754-698bd3d517d1", label="Test (Container)"
        ),
        SelectOption(value="1fd93743-262d-47e4-85a5-94814d9acd65", label="Test (Lab)"),
    ]


class AdminOrchestratorChallengeCreate(AdminChallengeCreate):
    orchestrator_id: Annotated[UUID, InlineSelect(_orchestrator_options)] = Field(
        title="orchestrator",
        description="orchestrator attached to this challenge.",
    )


class AdminOrchestratorChallengeUpdate(AdminChallengeUpdate):
    orchestrator_id: Annotated[UUID | None, InlineSelect(_orchestrator_options)] = (
        Field(
            default=None,
            title="orchestrator",
            description="orchestrator attached to this challenge.",
        )
    )


class AdminOrchestratorChallengeRead(AdminChallengeRead):
    orchestrator_id: UUID | None = None


class PublicOrchestratorInstanceRead(BaseModel):
    id: UUID
    challenge_id: UUID
    status: str
    start_date: datetime
    stop_date: datetime
    urls: list[str]
