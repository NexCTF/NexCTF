from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.exceptions import ConflictError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

from nexctf import crud
from nexctf.api.dep import SessionDep
from nexctf.model import CustomFieldDefinition
from nexctf.schema.custom_field import (
    AdminCustomFieldCreate,
    AdminCustomFieldRead,
    AdminCustomFieldUpdate,
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
