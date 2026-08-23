from typing import Annotated
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import AfterValidator

from nexctf.enums import InputType
from nexctf.schema.file import AdminFileRead, PublicFileRead
from nexctf.schema.hint import PublicHintRead
from nexctf.util.pydantic import Labels

TrapFlags = Annotated[
    list[str], AfterValidator(lambda v: [f for f in (s.strip() for s in v) if f])
]


class AdminQuestionRead(PydanticBase):
    id: UUID
    challenge_id: UUID
    label: str
    description: str | None = None
    index: int
    points: int
    malus: int | None
    input_type: InputType = InputType.INPUT
    trap_flags: list[str] = []
    challenge_title: str | None = None
    hint_count: int = 0
    solution_count: int = 0
    file_count: int = 0
    files: list[AdminFileRead] = []
    tags: list[str] = []


class AdminQuestionCreate(PydanticBase):
    challenge_id: UUID
    label: str
    description: str | None = None
    index: int = 0
    points: int = 100
    malus: int | None = None
    input_type: InputType = InputType.INPUT
    trap_flags: TrapFlags = []
    tags: Labels = []


class AdminQuestionUpdate(PydanticBase):
    id: UUID
    label: str | None = None
    description: str | None = None
    index: int | None = None
    points: int | None = None
    malus: int | None = None
    input_type: InputType | None = None
    trap_flags: TrapFlags | None = None
    files_ids: list[UUID] | None = None
    tags: Labels | None = None


class PublicQuestionRead(PydanticBase):
    id: UUID
    label: str
    description: str | None = None
    points: int
    malus: int | None
    input_type: InputType = InputType.INPUT
    is_solved: bool
    is_locked: bool = False
    is_blocked: bool = False
    has_trap: bool = False
    files: list[PublicFileRead] = []
    hints: list[PublicHintRead] = []
    tags: list[str] = []
    options: list[str] | None = None
    multi_select: bool = False
