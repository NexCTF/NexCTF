"""Custom Pydantic types that carry UI hints in their JSON schema.

Plugin authors import these types instead of plain `str` to signal
to the frontend how the field should be rendered, without any
frontend code knowing about specific field names.

Usage:
    from nexctf.util.pydantic import CodeStr, DynamicDefault, InlineSelect, SelectOption

    class MySolutionCreate(PydanticBase):
        checker_code: CodeStr = "def check(answer, team_id): ..."

        # Default value computed server-side when the schema is requested
        config: Annotated[CodeStr, DynamicDefault(lambda: generate_template())] = ""

        # UUID field rendered as a select; options are embedded in the schema
        resource_id: Annotated[UUID, InlineSelect(get_resource_options)]
"""

from __future__ import annotations

import copy
import dataclasses
from typing import TYPE_CHECKING, Annotated, Any, Awaitable, Callable

from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from nexctf.util.async_utils import call_maybe_async

if TYPE_CHECKING:
    from pydantic import BaseModel


@dataclasses.dataclass
class SelectOption:
    """One option in an inline-select field: the stored value + a human label."""

    value: str
    label: str

    def model_dump(self) -> dict:
        return {"value": self.value, "label": self.label}


@dataclasses.dataclass
class _UIWidget:
    """Pydantic v2 annotation that injects x-ui-widget into the field's JSON schema."""

    widget: str

    def __get_pydantic_json_schema__(
        self,
        schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema["x-ui-widget"] = self.widget
        return json_schema


@dataclasses.dataclass
class DynamicDefault:
    """Pydantic v2 annotation that marks a field whose initial value should be
    computed server-side by calling ``factory`` at schema-request time.

    The factory is called each time ``resolve_dynamic_defaults()`` is invoked
    on the schema class (typically in the GET /admin/solution/types endpoint).
    The computed value is injected as the ``default`` key in the returned schema
    dict so the frontend just reads ``prop.default`` as usual.

    Example:
        template: Annotated[CodeStr, DynamicDefault(lambda: generate_template())] = ""
    """

    factory: Callable[[], Any]

    def __get_pydantic_json_schema__(
        self,
        schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        # No marker injected — the factory runs server-side and injects the
        # computed value as "default" into the returned schema copy.
        return handler(schema)


@dataclasses.dataclass
class InlineSelect:
    """Pydantic v2 annotation that marks a field as a select rendered from inline options.

    The ``factory`` is called at schema-request time (when ``resolve_dynamic_defaults``
    runs) and the returned options are embedded in the JSON schema as ``x-ui-options``.
    The frontend renders a searchable combobox using those options without any extra fetch.

    The stored value is the ``SelectOption.value`` string (typically a UUID).

    Example::

        container_id: Annotated[UUID, InlineSelect(get_containers)]

        def get_containers() -> list[SelectOption]:
            return [SelectOption(value=str(c.id), label=c.name) for c in ...]
    """

    factory: Callable[[], list[SelectOption] | Awaitable[list[SelectOption]]]

    def __get_pydantic_json_schema__(
        self,
        schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        # No marker injected here — resolved server-side by resolve_dynamic_defaults.
        return handler(schema)


async def resolve_dynamic_defaults(model: type[BaseModel]) -> dict:
    """Return a deep copy of ``model.model_json_schema()`` with server-side annotations resolved:

    - ``DynamicDefault``: factory result injected as ``"default"``
    - ``InlineSelect``: factory result injected as ``"x-ui-options": [{value, label}, ...]``

    Both sync and async factories are supported.
    """
    schema = copy.deepcopy(model.model_json_schema())
    props = schema.get("properties", {})

    for field_name, field_info in model.model_fields.items():
        for annotation in field_info.metadata:
            if isinstance(annotation, DynamicDefault):
                if field_name in props:
                    props[field_name]["default"] = await call_maybe_async(
                        annotation.factory
                    )
                break
            elif isinstance(annotation, InlineSelect):
                if field_name in props:
                    options = await call_maybe_async(annotation.factory)
                    props[field_name]["x-ui-options"] = [
                        o.model_dump() for o in options
                    ]
                break

    return schema


# A string field rendered as a monospace code editor with Tab → 4-space support.
CodeStr = Annotated[str, _UIWidget(widget="code")]
