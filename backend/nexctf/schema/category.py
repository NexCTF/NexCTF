from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminCategoryCreate(PydanticBase):
    slug: str
    name: str


class AdminCategoryUpdate(PydanticBase):
    id: UUID
    slug: str | None = None
    name: str | None = None


class AdminCategoryRead(PydanticBase):
    id: UUID
    slug: str
    name: str
