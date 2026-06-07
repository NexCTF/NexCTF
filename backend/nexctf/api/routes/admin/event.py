"""Admin event log endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.schema.event import AdminEventRead

event_router = APIRouter(prefix="/event", tags=["Events"])


@event_router.get("")
async def get_events(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.EventCrud.paginate_params())],
) -> PaginatedResponse[AdminEventRead]:
    return await crud.EventCrud.paginate(
        session=session,
        **params,
        schema=AdminEventRead,
    )
