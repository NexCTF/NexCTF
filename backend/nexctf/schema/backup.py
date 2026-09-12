from datetime import datetime

from fastapi_toolsets.schemas import PydanticBase
from pydantic import Field


class AdminBackupRead(PydanticBase):
    key: str
    size: int
    created_at: datetime
    revision: str | None


class AdminBackupList(PydanticBase):
    backups: list[AdminBackupRead]
    last_restore: str | None = None


class BackupDatabaseParams(PydanticBase):
    keep_last: int = Field(default=7, ge=1, le=100)
