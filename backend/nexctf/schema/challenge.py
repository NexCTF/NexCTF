from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from nexctf.schema.question import PublicQuestionRead
from nexctf.schema.tag import AdminTagRead, PublicTagRead


class AdminChallengeCreate(PydanticBase):
    title: str
    description: str | None = None
    is_active: bool = False
    sequential: bool = False
    category_id: UUID | None = None
    author_id: UUID | None = None


class AdminChallengeUpdate(PydanticBase):
    id: UUID
    title: str | None = None
    description: str | None = None
    is_active: bool | None = None
    sequential: bool | None = None
    category_id: UUID | None = None
    author_id: UUID | None = None
    tags_ids: list[UUID] | None = None


class AdminChallengeRead(PydanticBase):
    id: UUID
    challenge_type: str
    title: str
    is_active: bool
    sequential: bool
    description: str | None
    author_id: UUID | None
    category_id: UUID | None
    category_name: str | None = None
    question_count: int = 0
    tags: list[AdminTagRead] = []


class PublicChallengeRead(PydanticBase):
    id: UUID
    title: str
    category_id: UUID | None
    category_name: str | None
    question_count: int
    solved_count: int
    tags: list[PublicTagRead] = []


class PublicChallengeDetail(PublicChallengeRead):
    challenge_type: str
    description: str | None = None
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
