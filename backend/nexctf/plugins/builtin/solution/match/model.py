from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from nexctf.model.solution import Solution


class MatchSolution(Solution):
    """Exact string comparison (case-insensitive by default)."""

    __tablename__ = "solutions_match"
    __mapper_args__ = {"polymorphic_identity": "match"}

    id: Mapped[UUID] = mapped_column(ForeignKey("solutions.id"), primary_key=True)
    value: Mapped[str] = mapped_column(String)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)

    async def verify(self, submission: str, *, team_id=None) -> bool:
        if self.case_sensitive:
            return submission == self.value
        return submission.casefold() == self.value.casefold()
