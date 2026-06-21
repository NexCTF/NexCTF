from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .question import Question


class Solution(Base):
    __tablename__ = "solutions"
    __mapper_args__ = {
        "polymorphic_on": "solve_type",
        "polymorphic_identity": "base",
    }

    solve_type: Mapped[str] = mapped_column(index=True)

    question: Mapped["Question"] = relationship(back_populates="solutions")
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"))

    @property
    def question_label(self) -> str | None:
        return self.question.label if self.question is not None else None

    @abstractmethod
    async def verify(self, submission: str, *, team_id: UUID | None = None) -> bool:
        """Return True if the submission is a valid solution.

        team_id is passed for solution types that need team context (e.g. script checker).
        Most implementations can ignore it.

        Raises:
            SolutionTimeoutError: If matching exceeds the implementation's time
                budget. Callers treat this as a non-match.
        """

    def public_options(self) -> list[str] | None:
        """Return the list of answer options to expose to the player, or None.

        Override in solution types that present a fixed set of choices (e.g. MCQ).
        The caller is responsible for deduplication and shuffling.
        """
        return None

    def is_multi_select(self) -> bool:
        """Return True if the player must select more than one option.

        Only meaningful when public_options() returns a non-empty list.
        """
        return False
