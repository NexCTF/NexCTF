from fastapi_toolsets.schemas import PydanticBase


class AdminConfigRead(PydanticBase):
    key: str
    type: str
    value: str | int | float | bool
    default: str
    label: str
    description: str
    choices: list[str]
    category: str
    category_label: str
    category_icon: str | None
    category_section: str
    is_plugin_category: bool


class AdminConfigBulkUpdate(PydanticBase):
    items: dict[str, str]
