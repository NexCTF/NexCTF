from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nexctf.model.solution import Solution


class RegexSolution(Solution):
    """Regular expression match against the submitted flag."""

    __tablename__ = "solutions_regex"
    __mapper_args__ = {"polymorphic_identity": "regex"}

    id: Mapped[UUID] = mapped_column(ForeignKey("solutions.id"), primary_key=True)
    pattern: Mapped[str] = mapped_column(String)
    flags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    async def verify(self, submission: str, *, team_id=None) -> bool:
        re_flags = 0
        if self.flags:
            for flag in self.flags:
                re_flags |= getattr(re, flag)
        return bool(re.fullmatch(self.pattern, submission, re_flags))
