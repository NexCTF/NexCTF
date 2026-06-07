from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminFileRead(PydanticBase):
    id: UUID
    name: str
    s3_key: str
    original_filename: str
    mime_type: str | None
    file_size: int | None
    is_public: bool
    created_at: datetime
    updated_at: datetime


class AdminFileDetail(AdminFileRead):
    view_url: str
    download_url: str


class AdminFileCreate(PydanticBase):
    id: UUID
    name: str
    s3_key: str
    original_filename: str
    mime_type: str | None = None
    file_size: int | None = None
    is_public: bool = False


class AdminFileUpdate(PydanticBase):
    name: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    is_public: bool | None = None


class PublicFileRead(PydanticBase):
    id: UUID
    name: str
    original_filename: str
    mime_type: str | None
    file_size: int | None
    url: str
