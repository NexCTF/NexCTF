from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import Field

from nexctf.schema.solution import AdminSolutionRead


class MCQSolutionCreate(PydanticBase):
    question_id: UUID
    correct_answers: list[str] = Field(
        default=[],
        title="Correct answers",
        description="Options that are accepted as correct. At least one is required.",
    )
    other_options: list[str] = Field(
        default=[],
        title="Other options",
        description="Wrong options shown alongside the correct answers.",
    )


class MCQSolutionUpdate(PydanticBase):
    id: UUID
    correct_answers: list[str] | None = Field(default=None, title="Correct answers")
    other_options: list[str] | None = Field(default=None, title="Other options")


class MCQSolutionRead(AdminSolutionRead):
    correct_answers: list[str]
    other_options: list[str]
