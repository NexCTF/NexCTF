from datetime import datetime
from uuid import UUID

from fastapi_toolsets.models import TimestampMixin, UUIDv7Mixin
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase, UUIDv7Mixin, TimestampMixin):
    type_annotation_map = {
        str: String(),
        int: Integer(),
        bool: Boolean(),
        UUID: PG_UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
    }
