from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import Field


class FeedbackBody(PydanticBase):
    rating: Annotated[int, Field(ge=1, le=5)]
    comment: Annotated[str | None, Field(max_length=2000)] = None


class FeedbackUpsert(FeedbackBody):
    team_id: UUID
    challenge_id: UUID


class PublicFeedbackRead(PydanticBase):
    rating: int
    comment: str | None = None


class AdminFeedbackRead(PydanticBase):
    id: UUID
    rating: int
    comment: str | None
    created_at: datetime
    team_id: UUID
    challenge_id: UUID
    team_name: str | None = None
    challenge_title: str | None = None
