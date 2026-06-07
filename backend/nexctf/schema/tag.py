from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminTagCreate(PydanticBase):
    name: str
    description: str
    color: str


class AdminTagUpdate(PydanticBase):
    id: UUID
    name: str
    description: str
    color: str


class AdminTagRead(PydanticBase):
    id: UUID
    name: str
    description: str
    color: str


class PublicTagRead(PydanticBase):
    id: UUID
    name: str
    description: str
    color: str
