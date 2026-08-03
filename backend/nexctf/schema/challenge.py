from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from nexctf.schema.question import PublicQuestionRead
from nexctf.util.pydantic import Label, Labels


class AdminChallengeCreate(PydanticBase):
    title: str
    description: str | None = None
    writeup: str | None = None
    is_active: bool = False
    sequential: bool = False
    category: Label = None
    tags: Labels = []
    author_id: UUID | None = None


class AdminChallengeUpdate(PydanticBase):
    id: UUID
    title: str | None = None
    description: str | None = None
    writeup: str | None = None
    is_active: bool | None = None
    sequential: bool | None = None
    category: Label = None
    tags: Labels | None = None
    author_id: UUID | None = None


class AdminChallengeRead(PydanticBase):
    id: UUID
    challenge_type: str
    title: str
    is_active: bool
    sequential: bool
    description: str | None
    writeup: str | None = None
    author_id: UUID | None
    category: str | None = None
    question_count: int = 0
    tags: list[str] = []


class PublicChallengeRead(PydanticBase):
    id: UUID
    title: str
    category: str | None
    question_count: int
    solved_count: int
    tags: list[str] = []


class PublicChallengeDetail(PublicChallengeRead):
    challenge_type: str
    description: str | None = None
    writeup: str | None = None
    sequential: bool
    questions: list[PublicQuestionRead]


class AdminChallengeTypeInfo(PydanticBase):
    type_name: str
    create_schema: dict
    update_schema: dict
    read_schema: dict


class SubmitBody(PydanticBase):
    answer: str


class SubmitResult(PydanticBase):
    is_correct: bool
    already_solved: bool
    points_earned: int
    message: str
