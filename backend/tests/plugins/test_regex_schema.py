"""Regex solutions refuse a pattern that cannot compile when it is saved."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from nexctf.plugins.builtin.solution.regex.schema import (
    RegexSolutionCreate,
    RegexSolutionUpdate,
)


def test_create_refuses_a_broken_pattern() -> None:
    with pytest.raises(ValidationError, match="Invalid regular expression"):
        RegexSolutionCreate(question_id=uuid4(), pattern="flag{(")


def test_update_refuses_a_broken_pattern() -> None:
    with pytest.raises(ValidationError, match="Invalid regular expression"):
        RegexSolutionUpdate(id=uuid4(), pattern="[a-")


def test_a_valid_pattern_is_kept() -> None:
    assert RegexSolutionCreate(question_id=uuid4(), pattern=r"flag\{.+\}").pattern
