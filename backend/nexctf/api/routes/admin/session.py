"""Admin session endpoints: the address-to-accounts pivot and the clients seen."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy import ColumnElement

from nexctf import crud
from nexctf.api.dep import ClientCategoryDep, SessionDep
from nexctf.enums import ClientCategory, SessionWindow
from nexctf.model import UserAgentSighting
from nexctf.module.client import clients_summary, sighting_load_options
from nexctf.module.session import (
    failed_logins_by_address,
    sessions_by_address,
    window_filters,
)
from nexctf.schema.user import (
    AdminClientSightingRead,
    AdminClientSummaryRead,
    AdminFailedLoginOverviewRead,
    AdminSessionOverviewRead,
)

session_router = APIRouter(prefix="/session", tags=["Session"])


@session_router.get("/addresses")
async def get_session_addresses(
    session: SessionDep,
    window: SessionWindow = SessionWindow.LIVE,
) -> Response[AdminSessionOverviewRead]:
    """Session totals over *window*, plus every address they are reached from."""
    return Response(data=await sessions_by_address(session, window))


@session_router.get("/failed-logins")
async def get_failed_logins(
    session: SessionDep,
    window: SessionWindow = SessionWindow.DAY,
) -> Response[AdminFailedLoginOverviewRead]:
    """Failed logins grouped by address: many usernames from one is stuffing."""
    return Response(data=await failed_logins_by_address(session, window))


def _client_filters(
    window: SessionWindow,
    category_expr: ColumnElement[str],
    category: list[ClientCategory] | None,
) -> list[Any]:
    filters = window_filters(window, UserAgentSighting.last_seen_at)
    if category:
        filters.append(category_expr.in_([c.value for c in category]))
    return filters


@session_router.get("/clients")
async def get_clients(
    session: SessionDep,
    category_expr: ClientCategoryDep,
    params: Annotated[
        dict,
        Depends(
            crud.UserAgentSightingCrud.paginate_params(
                default_order_field=UserAgentSighting.last_seen_at,
                default_order="desc",
            )
        ),
    ],
    window: SessionWindow = SessionWindow.DAY,
    category: Annotated[list[ClientCategory] | None, Query()] = None,
) -> PaginatedResponse[AdminClientSightingRead]:
    """Each account and user-agent pair seen over *window*, filterable by kind."""
    page = await crud.UserAgentSightingCrud.paginate(
        session=session,
        **params,
        filters=_client_filters(window, category_expr, category),
        load_options=sighting_load_options(category_expr),
        schema=AdminClientSightingRead,
    )
    if page.filter_attributes is not None:
        page.filter_attributes = {
            "category": [c.value for c in ClientCategory],
            **page.filter_attributes,
        }
    return page


@session_router.get("/clients/summary")
async def get_clients_summary(
    session: SessionDep,
    category: ClientCategoryDep,
    window: SessionWindow = SessionWindow.DAY,
) -> Response[AdminClientSummaryRead]:
    """How many clients and accounts were seen over *window*, per kind."""
    return Response(data=await clients_summary(session, window, category))
