from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.exceptions import ConflictError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model.page import CustomPage
from nexctf.schema.page import AdminPageCreate, AdminPageRead, AdminPageUpdate

page_router = APIRouter(prefix="/page", tags=["Page"])


@page_router.get("")
async def list_pages(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.PageCrud.paginate_params())],
) -> PaginatedResponse[AdminPageRead]:
    """List all custom pages (published and drafts)."""
    return await crud.PageCrud.paginate(session=session, **params, schema=AdminPageRead)


@page_router.post("", status_code=201)
async def create_page(
    session: SessionDep, obj: AdminPageCreate
) -> Response[AdminPageRead]:
    """Create a new custom page."""
    try:
        return await crud.PageCrud.create(
            session=session, obj=obj, schema=AdminPageRead
        )
    except IntegrityError:
        raise ConflictError()


@page_router.get("/{uuid}")
async def get_page(session: SessionDep, uuid: UUID) -> Response[AdminPageRead]:
    """Get a custom page by ID."""
    return await crud.PageCrud.get(
        session=session, filters=[CustomPage.id == uuid], schema=AdminPageRead
    )


@page_router.put("/{uuid}")
async def update_page(
    session: SessionDep, uuid: UUID, obj: AdminPageUpdate
) -> Response[AdminPageRead]:
    """Update a custom page."""
    try:
        return await crud.PageCrud.update(
            session=session,
            filters=[CustomPage.id == uuid],
            obj=obj,
            schema=AdminPageRead,
        )
    except IntegrityError:
        raise ConflictError()


@page_router.delete("/{uuid}")
async def delete_page(session: SessionDep, uuid: UUID) -> Response[None]:
    """Delete a custom page."""
    return await crud.PageCrud.delete(
        session=session, filters=[CustomPage.id == uuid], return_response=True
    )
