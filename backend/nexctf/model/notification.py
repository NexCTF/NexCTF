from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import Team, User

# Secondary table — no model class needed since there are no extra columns
notification_team_table = Table(
    "notification_targets",
    Base.metadata,
    Column("notification_id", ForeignKey("notifications.id"), primary_key=True),
    Column("team_id", ForeignKey("teams.id"), primary_key=True),
)


class Notification(Base):
    """Admin-created notification, either broadcast or targeted at specific teams."""

    __tablename__ = "notifications"

    title: Mapped[str]
    content: Mapped[str]
    is_broadcast: Mapped[bool] = mapped_column(default=False)

    teams: Mapped[list[Team]] = relationship(secondary=notification_team_table)

    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[User] = relationship()

    @property
    def created_by_username(self) -> str | None:
        return self.created_by.username if self.created_by is not None else None
