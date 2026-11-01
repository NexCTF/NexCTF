import re
from typing import Annotated
from uuid import UUID

import regex
from fastapi_toolsets.schemas import PydanticBase
from pydantic import AfterValidator, field_validator

from nexctf.schema.solution import AdminSolutionRead

_VALID_FLAGS: frozenset[str] = frozenset(f.name for f in re.RegexFlag)


def _validate_flags(v: list[str]) -> list[str]:
    invalid = [f for f in v if f not in _VALID_FLAGS]
    if invalid:
        raise ValueError(
            f"Invalid regex flags: {invalid}. Valid: {sorted(_VALID_FLAGS)}"
        )
    return v


def _validate_pattern(v: str) -> str:
    try:
        regex.compile(v)
    except regex.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}") from exc
    return v


Pattern = Annotated[str, AfterValidator(_validate_pattern)]


class RegexSolutionCreate(PydanticBase):
    question_id: UUID
    pattern: Pattern
    flags: list[str] = []

    @field_validator("flags")
    @classmethod
    def check_flags(cls, v: list[str]) -> list[str]:
        return _validate_flags(v)


class RegexSolutionUpdate(PydanticBase):
    id: UUID
    pattern: Pattern | None = None
    flags: list[str] | None = None

    @field_validator("flags")
    @classmethod
    def check_flags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return _validate_flags(v)
        return v


class RegexSolutionRead(AdminSolutionRead):
    pattern: str
    flags: list[str]
