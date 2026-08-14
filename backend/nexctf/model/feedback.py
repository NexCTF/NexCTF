from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .challenge import Challenge
    from .user import Team


class ChallengeFeedback(Base):
    """A team's rating and comment on a challenge it completed; one per team."""

    __tablename__ = "challenge_feedbacks"
    __table_args__ = (
        UniqueConstraint("team_id", "challenge_id", name="uq_challenge_feedback"),
    )

    rating: Mapped[int]
    comment: Mapped[str | None]

    team: Mapped[Team] = relationship()
    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id"))

    challenge: Mapped[Challenge] = relationship()
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("challenges.id"))

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team is not None else None

    @property
    def challenge_title(self) -> str | None:
        return self.challenge.title if self.challenge is not None else None
