from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminHintCreate(PydanticBase):
    question_id: UUID
    title: str
    content: str
    cost: int = 0
    order: int = 0


class AdminHintUpdate(PydanticBase):
    id: UUID
    title: str | None = None
    content: str | None = None
    cost: int | None = None
    order: int | None = None


class AdminHintRead(PydanticBase):
    id: UUID
    question_id: UUID
    title: str
    cost: int
    order: int
    question_label: str | None = None


class AdminHintReadDetail(AdminHintRead):
    content: str


class PublicHintRead(PydanticBase):
    id: UUID
    title: str
    cost: int
    is_unlocked: bool
    content: str | None = None
