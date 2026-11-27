from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from nexctf.enums import FileUsageKind


class AdminFileRead(PydanticBase):
    id: UUID
    name: str
    s3_key: str
    original_filename: str
    mime_type: str | None
    file_size: int | None
    is_public: bool
    sha256: str | None = None
    created_at: datetime
    updated_at: datetime


class FileUsage(PydanticBase):
    """A place a stored file is linked or referenced from."""

    kind: FileUsageKind
    target_id: UUID | None = None
    label: str
    challenge_id: UUID | None = None


class AdminFileListItem(AdminFileRead):
    """A stored file with its usages."""

    usages: list[FileUsage] = []


class AdminFileUploadRead(AdminFileRead):
    """An uploaded file with the stored files sharing its content."""

    duplicates: list[AdminFileRead] = []


class AdminFileSummary(PydanticBase):
    """Totals over every stored file."""

    count: int
    total_size: int
    unused_count: int


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
    sha256: str | None = None


class AdminFileUpdate(PydanticBase):
    name: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    is_public: bool | None = None
    sha256: str | None = None


class PublicFileRead(PydanticBase):
    id: UUID
    name: str
    original_filename: str
    mime_type: str | None
    file_size: int | None
    sha256: str | None = None
    url: str
