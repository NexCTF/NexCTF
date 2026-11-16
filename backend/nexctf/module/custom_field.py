"""Custom field reads and writes shared by the admin and self-service endpoints."""

import re
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.core import appconfig
from nexctf.exceptions import (
    InvalidCustomFieldValueError,
    ProfileIncompleteError,
    RequiredCustomFieldError,
    UnknownCustomFieldError,
)
from nexctf.model import CustomFieldDefinition, CustomFieldValue, User
from nexctf.model.custom_field import CustomFieldTarget, CustomFieldType
from nexctf.schema.custom_field import EditableCustomField

_HTTP_URL = re.compile(r"^https?://", re.IGNORECASE)


def _owner_scope(
    *, user_id: UUID | None = None, team_id: UUID | None = None
) -> tuple[CustomFieldTarget, ColumnElement[bool]]:
    """Resolve an owner to its definition target and a value filter."""
    if (user_id is None) == (team_id is None):
        raise ValueError("pass exactly one of user_id / team_id")
    if user_id is not None:
        return CustomFieldTarget.user, CustomFieldValue.user_id == user_id
    return CustomFieldTarget.team, CustomFieldValue.team_id == team_id


def _validate_value(field_type: CustomFieldType, value: str) -> None:
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
    session: AsyncSession, target: CustomFieldTarget, *, self_service: bool
) -> list[CustomFieldDefinition]:
    filters = [CustomFieldDefinition.target == target]
    if self_service:
        filters.append(CustomFieldDefinition.is_self_editable.is_(True))
    return list(
        await crud.CustomFieldDefinitionCrud.get_multi(
            session=session,
            filters=filters,
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
    """Return an owner's self-editable definitions, with that owner's values."""
    target, value_filter = _owner_scope(user_id=user_id, team_id=team_id)
    definitions = await _definitions_for(session, target, self_service=True)
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
    self_service: bool = True,
) -> list[EditableCustomField]:
    """Replace an owner's custom field values with *values*, returning the result."""
    target, value_filter = _owner_scope(user_id=user_id, team_id=team_id)
    definitions = await _definitions_for(session, target, self_service=self_service)
    by_id = {d.id: d for d in definitions}
    if not set(values) <= set(by_id):
        raise UnknownCustomFieldError()
    for definition_id, value in values.items():
        if value:
            _validate_value(by_id[definition_id].field_type, value)
    if self_service and any(
        d.is_required and not values.get(d.id) for d in definitions
    ):
        raise RequiredCustomFieldError()

    existing = {
        row.definition_id: row
        for row in await crud.CustomFieldValueCrud.get_multi(
            session=session, filters=[value_filter], load_options=[]
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


def _fillable_scopes(
    user: User, overrides: dict[str, str]
) -> list[tuple[CustomFieldTarget, ColumnElement[bool]]]:
    """The targets *user* may edit now, each with the filter matching their values."""
    candidates = (
        (
            CustomFieldTarget.user,
            "ctf.allow_user_customization",
            CustomFieldValue.user_id == user.id,
        ),
        (
            CustomFieldTarget.team,
            "ctf.allow_team_customization",
            CustomFieldValue.team_id == user.team_id,
        ),
    )
    return [
        (target, owner)
        for target, setting, owner in candidates
        if appconfig.get_with_overrides(setting, overrides)
    ]


async def require_complete_profile(
    session: AsyncSession, user: User, overrides: dict[str, str]
) -> None:
    """Raise ProfileIncompleteError while a required field *user* can fill is empty.

    Covers the user's own fields and their team's, and only the self-editable
    definitions of a profile the players may currently edit.
    """
    scopes = _fillable_scopes(user, overrides)
    if not scopes:
        return
    filled = exists().where(
        CustomFieldValue.definition_id == CustomFieldDefinition.id,
        func.btrim(CustomFieldValue.value) != "",
        or_(
            *(
                and_(CustomFieldDefinition.target == target, owner)
                for target, owner in scopes
            )
        ),
    )
    missing = exists().where(
        CustomFieldDefinition.is_required.is_(True),
        CustomFieldDefinition.is_self_editable.is_(True),
        CustomFieldDefinition.target.in_([target for target, _ in scopes]),
        ~filled,
    )
    if await session.scalar(select(missing)):
        raise ProfileIncompleteError()
