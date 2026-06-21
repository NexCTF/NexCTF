from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import regex
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nexctf.exceptions import SolutionTimeoutError
from nexctf.model.solution import Solution

logger = logging.getLogger(__name__)

_MATCH_TIMEOUT_SECONDS = 1.0


def _resolve_flags(flags: list[str] | None) -> int:
    """Resolve stored flag names to a combined regex flag bitmask.

    Names are validated against an allowlist at creation time; this re-checks
    each one so a corrupted/unexpected value raises a clear error instead of
    feeding an arbitrary attribute lookup into the matcher.
    """
    re_flags = 0
    for flag in flags or ():
        value = getattr(regex, flag, None)
        if not isinstance(value, regex.RegexFlag):
            raise ValueError(f"Unknown regex flag: {flag!r}")
        re_flags |= value
    return re_flags


class RegexSolution(Solution):
    """Regular expression match against the submitted flag."""

    __tablename__ = "solutions_regex"
    __mapper_args__ = {"polymorphic_identity": "regex"}

    id: Mapped[UUID] = mapped_column(ForeignKey("solutions.id"), primary_key=True)
    pattern: Mapped[str] = mapped_column(String)
    flags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    async def verify(self, submission: str, *, team_id: UUID | None = None) -> bool:
        """Return True if the submission fully matches the configured pattern.

        Raises:
            SolutionTimeoutError: If the match exceeds the timeout.
        """
        re_flags = _resolve_flags(self.flags)
        try:
            return await asyncio.to_thread(self._fullmatch, submission, re_flags)
        except TimeoutError as exc:
            logger.warning(
                "Regex solution %s exceeded the %.1fs match timeout.",
                self.id,
                _MATCH_TIMEOUT_SECONDS,
            )
            raise SolutionTimeoutError(self.id, self.pattern) from exc

    def _fullmatch(self, submission: str, re_flags: int) -> bool:
        return bool(
            regex.fullmatch(
                self.pattern,
                submission,
                re_flags,
                timeout=_MATCH_TIMEOUT_SECONDS,
            )
        )
