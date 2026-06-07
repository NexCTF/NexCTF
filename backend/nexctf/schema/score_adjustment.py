from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminScoreAdjustmentCreate(PydanticBase):
    team_id: UUID
    amount: int
    reason: str
    challenge_id: UUID | None = None


class AdminScoreAdjustmentCreateInternal(AdminScoreAdjustmentCreate):
    created_by_id: UUID


class AdminScoreAdjustmentUpdate(PydanticBase):
    id: UUID
    amount: int | None = None
    reason: str | None = None


class AdminScoreAdjustmentRead(PydanticBase):
    id: UUID
    team_id: UUID
    amount: int
    reason: str
    challenge_id: UUID | None
    created_by_id: UUID
    team_name: str | None = None
    challenge_title: str | None = None
    created_by_username: str | None = None
