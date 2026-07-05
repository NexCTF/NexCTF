from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from ..model.link import Visibility


class AdminLinkCreate(PydanticBase):
    name: str
    url: str
    visibility: Visibility
    is_enabled: bool = True


class AdminLinkUpdate(PydanticBase):
    id: UUID
    name: str
    url: str
    visibility: Visibility
    is_enabled: bool


class AdminLinkRead(PydanticBase):
    id: UUID
    name: str
    url: str
    visibility: Visibility
    is_enabled: bool


class PublicLinkRead(PydanticBase):
    name: str
    url: str
