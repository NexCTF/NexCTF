"""Tests for the builtin regex solution's match behaviour."""

from __future__ import annotations

import time

import pytest

from nexctf.exceptions import SolutionTimeoutError
from nexctf.plugins.builtin.solution.regex import model as regex_model
from nexctf.plugins.builtin.solution.regex.model import RegexSolution


async def test_matches_with_flags() -> None:
    """Stored flag names are honoured when matching."""
    solution = RegexSolution(pattern=r"flag\{.*\}", flags=["IGNORECASE"])
    assert await solution.verify("FLAG{ok}") is True
    assert await solution.verify("nope") is False


async def test_catastrophic_pattern_does_not_hang() -> None:
    """A classic ReDoS pattern + input must return promptly, not block.

    ``(a+)+$`` against a long non-matching string spins for tens of seconds on
    stdlib ``re``; the engine must resolve it well within the match timeout so a
    malicious submission cannot DoS the event loop.
    """
    solution = RegexSolution(pattern=r"(a+)+$")
    start = time.perf_counter()
    result = await solution.verify("a" * 40 + "b")
    elapsed = time.perf_counter() - start

    assert result is False
    assert elapsed < regex_model._MATCH_TIMEOUT_SECONDS + 1.0


async def test_timeout_raises_solution_timeout_error(monkeypatch) -> None:
    """A match that exceeds the timeout surfaces as SolutionTimeoutError.

    Callers catch this to emit an admin-visible event and treat the submission
    as a non-match.
    """

    def _raise_timeout(self, submission: str, re_flags: int) -> bool:
        raise TimeoutError

    monkeypatch.setattr(RegexSolution, "_fullmatch", _raise_timeout)
    solution = RegexSolution(pattern=r".*")
    with pytest.raises(SolutionTimeoutError):
        await solution.verify("anything")


async def test_unknown_flag_raises() -> None:
    """A flag name that isn't a real regex flag raises instead of doing an
    arbitrary attribute lookup."""
    solution = RegexSolution(pattern=r"flag", flags=["__doc__"])
    with pytest.raises(ValueError, match="Unknown regex flag"):
        await solution.verify("flag")
