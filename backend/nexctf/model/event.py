from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .base import Base


class _InetString(TypeDecorator):
    """INET column that always returns a plain str to Python, never IPv4Address."""

    impl = INET
    cache_ok = True

    def process_result_value(self, value: object, dialect: object) -> str | None:
        return str(value) if value is not None else None


if TYPE_CHECKING:
    from .challenge import Challenge
    from .user import Team, User


class Event(Base):
    """System-generated audit event (admin-only)."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_event_type", "event_type"),)

    event_type: Mapped[str]
    ip: Mapped[str | None] = mapped_column(_InetString, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])

    team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    team: Mapped[Team | None] = relationship(foreign_keys=[team_id])

    challenge_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("challenges.id", ondelete="SET NULL"), nullable=True
    )
    challenge: Mapped[Challenge | None] = relationship(foreign_keys=[challenge_id])

    @property
    def actor_username(self) -> str | None:
        return self.actor.username if self.actor else None

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team else None

    @property
    def challenge_title(self) -> str | None:
        return self.challenge.title if self.challenge else None
