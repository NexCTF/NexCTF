from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nexctf.model.solution import Solution


class MCQSolution(Solution):
    """Multiple-choice: submission must be one of the correct answers."""

    __tablename__ = "solutions_mcq"
    __mapper_args__ = {"polymorphic_identity": "mcq"}

    id: Mapped[UUID] = mapped_column(ForeignKey("solutions.id"), primary_key=True)
    correct_answers: Mapped[list[str]] = mapped_column(JSONB, default=list)
    other_options: Mapped[list[str]] = mapped_column(JSONB, default=list)

    async def verify(self, submission: str, *, team_id=None) -> bool:
        if self.is_multi_select():
            import json

            try:
                selected = {s.strip() for s in json.loads(submission)}
            except Exception:
                return False
            return selected == {a.strip() for a in self.correct_answers}
        return submission.strip() in [a.strip() for a in self.correct_answers]

    def public_options(self) -> list[str]:
        return list(self.correct_answers) + list(self.other_options)

    def is_multi_select(self) -> bool:
        return len(self.correct_answers) > 1
