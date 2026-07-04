from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.exceptions import ConflictError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model.link import Link
from nexctf.schema.link import AdminLinkCreate, AdminLinkRead, AdminLinkUpdate

link_router = APIRouter(prefix="/link", tags=["Link"])


@link_router.get("")
async def list_links(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.LinkCrud.paginate_params())],
) -> PaginatedResponse[AdminLinkRead]:
    """List all custom links (published and drafts)."""
    return await crud.LinkCrud.paginate(session=session, **params, schema=AdminLinkRead)


@link_router.post("", status_code=201)
async def create_link(
    session: SessionDep, obj: AdminLinkCreate
) -> Response[AdminLinkRead]:
    """Create a new custom link."""
    try:
        return await crud.LinkCrud.create(
            session=session, obj=obj, schema=AdminLinkRead
        )
    except IntegrityError:
        raise ConflictError()


@link_router.get("/{uuid}")
async def get_link(session: SessionDep, uuid: UUID) -> Response[AdminLinkRead]:
    """Get a custom link by ID."""
    return await crud.LinkCrud.get(
        session=session, filters=[Link.id == uuid], schema=AdminLinkRead
    )


@link_router.put("/{uuid}")
async def update_link(
    session: SessionDep, uuid: UUID, obj: AdminLinkUpdate
) -> Response[AdminLinkRead]:
    """Update a custom link."""
    try:
        return await crud.LinkCrud.update(
            session=session,
            filters=[Link.id == uuid],
            obj=obj,
            schema=AdminLinkRead,
        )
    except IntegrityError:
        raise ConflictError()


@link_router.delete("/{uuid}")
async def delete_link(session: SessionDep, uuid: UUID) -> Response[None]:
    """Delete a custom link."""
    return await crud.LinkCrud.delete(
        session=session, filters=[Link.id == uuid], return_response=True
    )
