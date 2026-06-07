from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model import Hint
from nexctf.schema.hint import (
    AdminHintCreate,
    AdminHintRead,
    AdminHintReadDetail,
    AdminHintUpdate,
)

hint_router = APIRouter(prefix="/hint", tags=["Hint"])


@hint_router.get("")
async def get_hints(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.HintCrud.paginate_params())],
) -> PaginatedResponse[AdminHintRead]:
    return await crud.HintCrud.paginate(
        session=session,
        **params,
        schema=AdminHintRead,
    )


@hint_router.post("")
async def create_hint(
    session: SessionDep,
    obj: AdminHintCreate,
) -> Response[AdminHintReadDetail]:
    return await crud.HintCrud.create(
        session=session, obj=obj, schema=AdminHintReadDetail
    )


@hint_router.get("/{uuid}")
async def get_hint(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminHintReadDetail]:
    return await crud.HintCrud.get(
        session=session,
        filters=[Hint.id == uuid],
        schema=AdminHintReadDetail,
    )


@hint_router.put("/{uuid}")
async def update_hint(
    session: SessionDep,
    uuid: UUID,
    obj: AdminHintUpdate,
) -> Response[AdminHintReadDetail]:
    return await crud.HintCrud.update(
        session=session,
        filters=[Hint.id == uuid],
        obj=obj,
        schema=AdminHintReadDetail,
    )


@hint_router.delete("/{uuid}")
async def delete_hint(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.HintCrud.delete(
        session=session, filters=[Hint.id == uuid], return_response=True
    )
