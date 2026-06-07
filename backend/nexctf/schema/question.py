from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from nexctf.enums import InputType
from nexctf.schema.file import AdminFileRead, PublicFileRead
from nexctf.schema.hint import PublicHintRead
from nexctf.schema.tag import AdminTagRead, PublicTagRead


class AdminQuestionRead(PydanticBase):
    id: UUID
    challenge_id: UUID
    label: str
    description: str | None = None
    index: int
    points: int
    malus: int | None
    input_type: InputType = InputType.INPUT
    challenge_title: str | None = None
    hint_count: int = 0
    solution_count: int = 0
    file_count: int = 0
    files: list[AdminFileRead] = []
    tags: list[AdminTagRead] = []


class AdminQuestionCreate(PydanticBase):
    challenge_id: UUID
    label: str
    description: str | None = None
    index: int = 0
    points: int = 100
    malus: int | None = None
    input_type: InputType = InputType.INPUT


class AdminQuestionUpdate(PydanticBase):
    id: UUID
    label: str | None = None
    description: str | None = None
    index: int | None = None
    points: int | None = None
    malus: int | None = None
    input_type: InputType | None = None
    files_ids: list[UUID] | None = None
    tags_ids: list[UUID] | None = None


class PublicQuestionRead(PydanticBase):
    id: UUID
    label: str
    description: str | None = None
    points: int
    malus: int | None
    input_type: InputType = InputType.INPUT
    is_solved: bool
    is_locked: bool = False
    files: list[PublicFileRead] = []
    hints: list[PublicHintRead] = []
    tags: list[PublicTagRead] = []
    options: list[str] | None = None
    multi_select: bool = False
