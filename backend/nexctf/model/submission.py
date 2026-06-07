from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .challenge import Challenge
    from .question import Question
    from .user import Team, User


class Submission(Base):
    """Records every flag attempt."""

    __tablename__ = "submissions"
    __table_args__ = (Index("ix_submissions_team_question", "team_id", "question_id"),)

    answer: Mapped[str]
    is_correct: Mapped[bool] = mapped_column(default=False)
    points_earned: Mapped[int] = mapped_column(default=0)
    wrong_count_before: Mapped[int] = mapped_column(default=0)

    team: Mapped[Team] = relationship(back_populates="submissions")
    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id"))

    question: Mapped[Question] = relationship()
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"))

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team is not None else None

    @property
    def question_label(self) -> str | None:
        return self.question.label if self.question is not None else None

    @property
    def question_challenge_title(self) -> str | None:
        if self.question is None:
            return None
        return self.question.challenge_title


class ScoreAdjustment(Base):
    """Manual bonus or malus applied by an admin."""

    __tablename__ = "score_adjustments"

    amount: Mapped[int]
    reason: Mapped[str]

    team: Mapped[Team] = relationship(back_populates="score_adjustments")
    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id"))

    challenge: Mapped[Challenge | None] = relationship()
    challenge_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("challenges.id"), nullable=True
    )

    created_by: Mapped[User] = relationship()
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team is not None else None

    @property
    def challenge_title(self) -> str | None:
        return self.challenge.title if self.challenge is not None else None

    @property
    def created_by_username(self) -> str | None:
        return self.created_by.username if self.created_by is not None else None
