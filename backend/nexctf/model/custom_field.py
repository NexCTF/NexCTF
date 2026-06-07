from __future__ import annotations

import enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import Team, User


class CustomFieldType(enum.Enum):
    string = "string"
    integer = "integer"
    boolean = "boolean"
    url = "url"


class CustomFieldTarget(enum.Enum):
    user = "user"
    team = "team"


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"

    name: Mapped[str] = mapped_column(unique=True, index=True)
    label: Mapped[str]
    field_type: Mapped[CustomFieldType] = mapped_column(
        Enum(CustomFieldType), default=CustomFieldType.string
    )
    target: Mapped[CustomFieldTarget] = mapped_column(Enum(CustomFieldTarget))
    is_required: Mapped[bool] = mapped_column(default=False)
    is_public: Mapped[bool] = mapped_column(default=True)

    values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="definition", cascade="all, delete-orphan"
    )


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"

    value: Mapped[str | None]

    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True
    )

    definition: Mapped["CustomFieldDefinition"] = relationship(back_populates="values")
    user: Mapped["User | None"] = relationship(back_populates="custom_field_values")
    team: Mapped["Team | None"] = relationship(back_populates="custom_field_values")
