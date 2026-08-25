from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi_toolsets.exceptions import ConflictError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

from nexctf import crud
from nexctf.api.dep import SessionDep
from nexctf.exceptions import UnknownCustomFieldError
from nexctf.model import CustomFieldDefinition, CustomFieldValue
from nexctf.module.custom_field import owner_scope, validate_value
from nexctf.schema.custom_field import (
    AdminCustomFieldCreate,
    AdminCustomFieldRead,
    AdminCustomFieldUpdate,
    AdminCustomFieldValueCreate,
    AdminCustomFieldValueRead,
    AdminCustomFieldValueUpdate,
)

custom_field_router = APIRouter(prefix="/custom-field", tags=["Custom Field"])


@custom_field_router.get("")
async def get_custom_fields(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.CustomFieldDefinitionCrud.paginate_params())],
) -> PaginatedResponse[AdminCustomFieldRead]:
    return await crud.CustomFieldDefinitionCrud.paginate(
        session=session,
        **params,
        schema=AdminCustomFieldRead,
    )


@custom_field_router.post("")
async def create_custom_field(
    session: SessionDep,
    obj: AdminCustomFieldCreate,
) -> Response[AdminCustomFieldRead]:
    try:
        return await crud.CustomFieldDefinitionCrud.create(
            session=session, obj=obj, schema=AdminCustomFieldRead
        )
    except IntegrityError:
        raise ConflictError(detail="Field key already taken")


@custom_field_router.get("/{uuid}")
async def get_custom_field(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminCustomFieldRead]:
    return await crud.CustomFieldDefinitionCrud.get(
        session=session,
        filters=[CustomFieldDefinition.id == uuid],
        schema=AdminCustomFieldRead,
    )


@custom_field_router.put("/{uuid}")
async def update_custom_field(
    session: SessionDep,
    uuid: UUID,
    obj: AdminCustomFieldUpdate,
) -> Response[AdminCustomFieldRead]:
    try:
        return await crud.CustomFieldDefinitionCrud.update(
            session=session,
            filters=[CustomFieldDefinition.id == uuid],
            obj=obj,
            schema=AdminCustomFieldRead,
        )
    except IntegrityError:
        raise ConflictError(detail="Field key already taken")


@custom_field_router.delete("/{uuid}")
async def delete_custom_field(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.CustomFieldDefinitionCrud.delete(
        session=session,
        filters=[CustomFieldDefinition.id == uuid],
        return_response=True,
    )


custom_field_value_router = APIRouter(
    prefix="/custom-field-value", tags=["Custom Field"]
)


@custom_field_value_router.get("")
async def get_custom_field_values(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.CustomFieldValueCrud.paginate_params())],
) -> PaginatedResponse[AdminCustomFieldValueRead]:
    return await crud.CustomFieldValueCrud.paginate(
        session=session,
        **params,
        schema=AdminCustomFieldValueRead,
    )


@custom_field_value_router.post("")
async def set_custom_field_value(
    session: SessionDep,
    obj: AdminCustomFieldValueCreate,
) -> Response[AdminCustomFieldValueRead]:
    if obj.user_id is None and obj.team_id is None:
        raise HTTPException(status_code=422, detail="Provide user_id or team_id")
    if obj.user_id is not None and obj.team_id is not None:
        raise HTTPException(
            status_code=422, detail="Provide only one of user_id or team_id"
        )

    _, owner_filter = owner_scope(user_id=obj.user_id, team_id=obj.team_id)
    existing = await crud.CustomFieldValueCrud.first(
        session=session,
        filters=[CustomFieldValue.definition_id == obj.definition_id, owner_filter],
    )
    # CustomFieldValueCrud joins the definition in, so an update already has it.
    definition = existing.definition if existing is not None else None
    if definition is None:
        definition = await crud.CustomFieldDefinitionCrud.first(
            session=session, filters=[CustomFieldDefinition.id == obj.definition_id]
        )
    if definition is None:
        raise UnknownCustomFieldError()
    if obj.value:
        validate_value(definition.field_type, obj.value)

    if existing is not None:
        return await crud.CustomFieldValueCrud.update(
            session=session,
            filters=[CustomFieldValue.id == existing.id],
            obj=AdminCustomFieldValueUpdate(id=existing.id, value=obj.value),
            schema=AdminCustomFieldValueRead,
        )

    return await crud.CustomFieldValueCrud.create(
        session=session, obj=obj, schema=AdminCustomFieldValueRead
    )


@custom_field_value_router.delete("/{uuid}")
async def delete_custom_field_value(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.CustomFieldValueCrud.delete(
        session=session,
        filters=[CustomFieldValue.id == uuid],
        return_response=True,
    )
