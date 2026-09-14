from datetime import datetime
from enum import StrEnum

from fastapi_toolsets.schemas import PydanticBase
from pydantic import Field


class BackupSource(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"
    PRE_RESTORE = "pre_restore"


class AdminBackupRead(PydanticBase):
    key: str
    size: int
    created_at: datetime
    revision: str | None
    source: BackupSource | None


class AdminBackupList(PydanticBase):
    backups: list[AdminBackupRead]
    last_restore: str | None = None


class BackupDatabaseParams(PydanticBase):
    keep_last: int = Field(default=7, ge=1, le=100)
