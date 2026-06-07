from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminSolutionRead(PydanticBase):
    id: UUID
    solve_type: str
    question_id: UUID


class AdminSolutionTypeInfo(PydanticBase):
    type_name: str
    description: str | None = None
    create_schema: dict
    update_schema: dict
    read_schema: dict
    compatible_input_types: list[str] | None = None
