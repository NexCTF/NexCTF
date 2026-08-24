"""Custom field reads and writes shared by the admin and self-service endpoints."""

import re
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.exceptions import InvalidCustomFieldValueError, UnknownCustomFieldError
from nexctf.model import CustomFieldDefinition, CustomFieldValue
from nexctf.model.custom_field import CustomFieldTarget, CustomFieldType
from nexctf.schema.custom_field import EditableCustomField

_HTTP_URL = re.compile(r"^https?://", re.IGNORECASE)


def owner_scope(
    *, user_id: UUID | None = None, team_id: UUID | None = None
) -> tuple[CustomFieldTarget, ColumnElement[bool]]:
    """Resolve an owner to its definition target and a value filter."""
    if (user_id is None) == (team_id is None):
        raise ValueError("pass exactly one of user_id / team_id")
    if user_id is not None:
        return CustomFieldTarget.user, CustomFieldValue.user_id == user_id
    return CustomFieldTarget.team, CustomFieldValue.team_id == team_id


def validate_value(field_type: CustomFieldType, value: str) -> None:
    """Raise InvalidCustomFieldValueError if value does not match its type."""
    if field_type == CustomFieldType.integer:
        try:
            int(value)
        except ValueError:
            raise InvalidCustomFieldValueError()
    elif field_type == CustomFieldType.boolean:
        if value.lower() not in ("true", "false"):
            raise InvalidCustomFieldValueError()
    elif field_type == CustomFieldType.url and not _HTTP_URL.match(value):
        raise InvalidCustomFieldValueError()


async def _definitions_for(
    session: AsyncSession, target: CustomFieldTarget
) -> list[CustomFieldDefinition]:
    return list(
        await crud.CustomFieldDefinitionCrud.get_multi(
            session=session,
            filters=[CustomFieldDefinition.target == target],
            order_by=CustomFieldDefinition.name,
        )
    )


def _editable(
    definitions: list[CustomFieldDefinition], values: dict[UUID, str | None]
) -> list[EditableCustomField]:
    return [
        EditableCustomField(
            definition_id=d.id,
            label=d.label,
            field_type=d.field_type,
            is_required=d.is_required,
            value=values.get(d.id),
        )
        for d in definitions
    ]


async def load_editable_fields(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    team_id: UUID | None = None,
) -> list[EditableCustomField]:
    """Return every definition for an owner's target, with that owner's values."""
    target, value_filter = owner_scope(user_id=user_id, team_id=team_id)
    definitions = await _definitions_for(session, target)
    rows = await crud.CustomFieldValueCrud.get_multi(
        session=session, filters=[value_filter]
    )
    return _editable(definitions, {row.definition_id: row.value for row in rows})


async def replace_custom_field_values(
    session: AsyncSession,
    values: dict[UUID, str | None],
    *,
    user_id: UUID | None = None,
    team_id: UUID | None = None,
) -> list[EditableCustomField]:
    """Replace an owner's custom field values with *values*, returning the result."""
    target, value_filter = owner_scope(user_id=user_id, team_id=team_id)
    definitions = await _definitions_for(session, target)
    by_id = {d.id: d for d in definitions}
    if not set(values) <= set(by_id):
        raise UnknownCustomFieldError()
    for definition_id, value in values.items():
        if value:
            validate_value(by_id[definition_id].field_type, value)

    existing = {
        row.definition_id: row
        for row in await crud.CustomFieldValueCrud.get_multi(
            session=session, filters=[value_filter]
        )
    }
    written: dict[UUID, str | None] = {}
    for definition_id in by_id:
        value = values.get(definition_id) or None
        written[definition_id] = value
        row = existing.get(definition_id)
        if value is None:
            if row is not None:
                await session.delete(row)
        elif row is not None:
            row.value = value
        else:
            session.add(
                CustomFieldValue(
                    definition_id=definition_id,
                    user_id=user_id,
                    team_id=team_id,
                    value=value,
                )
            )
    await session.flush()
    return _editable(definitions, written)
