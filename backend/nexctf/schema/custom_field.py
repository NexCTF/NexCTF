from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase

from nexctf.model.custom_field import CustomFieldTarget, CustomFieldType


class AdminCustomFieldCreate(PydanticBase):
    name: str
    label: str
    field_type: CustomFieldType = CustomFieldType.string
    target: CustomFieldTarget
    is_required: bool = False
    is_public: bool = True
    show_in_scoreboard: bool = False


class AdminCustomFieldUpdate(PydanticBase):
    id: UUID
    name: str | None = None
    label: str | None = None
    field_type: CustomFieldType | None = None
    is_required: bool | None = None
    is_public: bool | None = None
    show_in_scoreboard: bool | None = None


class AdminCustomFieldRead(PydanticBase):
    id: UUID
    name: str
    label: str
    field_type: CustomFieldType
    target: CustomFieldTarget
    is_required: bool
    is_public: bool
    show_in_scoreboard: bool


class PublicCustomFieldValue(PydanticBase):
    name: str
    label: str
    field_type: CustomFieldType
    value: str | None


class AdminCustomFieldValueCreate(PydanticBase):
    definition_id: UUID
    user_id: UUID | None = None
    team_id: UUID | None = None
    value: str | None = None


class AdminCustomFieldValueUpdate(PydanticBase):
    id: UUID
    value: str | None = None


class AdminCustomFieldValueRead(PydanticBase):
    id: UUID
    definition: AdminCustomFieldRead
    user_id: UUID | None
    team_id: UUID | None
    value: str | None
