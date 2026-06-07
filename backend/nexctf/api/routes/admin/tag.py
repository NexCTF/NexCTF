from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model import Tag
from nexctf.schema.tag import AdminTagCreate, AdminTagRead, AdminTagUpdate

tag_router = APIRouter(prefix="/tag", tags=["Tag"])


@tag_router.get("")
async def get_tags(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.TagCrud.paginate_params())],
) -> PaginatedResponse[AdminTagRead]:
    return await crud.TagCrud.paginate(
        session=session,
        **params,
        schema=AdminTagRead,
    )


@tag_router.post("")
async def create_tag(
    session: SessionDep,
    obj: AdminTagCreate,
) -> Response[AdminTagRead]:
    return await crud.TagCrud.create(session=session, obj=obj, schema=AdminTagRead)


@tag_router.get("/{uuid}")
async def get_tag(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminTagRead]:
    return await crud.TagCrud.get(
        session=session,
        filters=[Tag.id == uuid],
        schema=AdminTagRead,
    )


@tag_router.put("/{uuid}")
async def update_tag(
    session: SessionDep,
    uuid: UUID,
    obj: AdminTagUpdate,
) -> Response[AdminTagRead]:
    return await crud.TagCrud.update(
        session=session,
        filters=[Tag.id == uuid],
        obj=obj,
        schema=AdminTagRead,
    )


@tag_router.delete("/{uuid}")
async def delete_tag(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.TagCrud.delete(
        session=session,
        filters=[Tag.id == uuid],
        return_response=True,
    )
