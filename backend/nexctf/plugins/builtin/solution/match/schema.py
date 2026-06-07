from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from nexctf.schema.solution import AdminSolutionRead


class MatchSolutionCreate(PydanticBase):
    question_id: UUID
    value: str
    case_sensitive: bool = False


class MatchSolutionUpdate(PydanticBase):
    id: UUID
    value: str | None = None
    case_sensitive: bool | None = None


class MatchSolutionRead(AdminSolutionRead):
    value: str
    case_sensitive: bool
