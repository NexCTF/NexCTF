from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model import ChallengeCategory
from nexctf.schema.category import (
    AdminCategoryCreate,
    AdminCategoryRead,
    AdminCategoryUpdate,
)

category_router = APIRouter(prefix="/category", tags=["Category"])


@category_router.get("")
async def get_categories(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.ChallengeCategoryCrud.paginate_params())],
) -> PaginatedResponse[AdminCategoryRead]:
    return await crud.ChallengeCategoryCrud.paginate(
        session=session,
        **params,
        schema=AdminCategoryRead,
    )


@category_router.post("")
async def create_category(
    session: SessionDep,
    obj: AdminCategoryCreate,
) -> Response[AdminCategoryRead]:
    return await crud.ChallengeCategoryCrud.create(
        session=session, obj=obj, schema=AdminCategoryRead
    )


@category_router.get("/{uuid}")
async def get_category(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminCategoryRead]:
    return await crud.ChallengeCategoryCrud.get(
        session=session,
        filters=[ChallengeCategory.id == uuid],
        schema=AdminCategoryRead,
    )


@category_router.put("/{uuid}")
async def update_category(
    session: SessionDep,
    uuid: UUID,
    obj: AdminCategoryUpdate,
) -> Response[AdminCategoryRead]:
    return await crud.ChallengeCategoryCrud.update(
        session=session,
        filters=[ChallengeCategory.id == uuid],
        obj=obj,
        schema=AdminCategoryRead,
    )


@category_router.delete("/{uuid}")
async def delete_category(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.ChallengeCategoryCrud.delete(
        session=session,
        filters=[ChallengeCategory.id == uuid],
        return_response=True,
    )
