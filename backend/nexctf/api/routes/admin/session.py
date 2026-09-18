"""Admin session endpoints: the address-to-accounts pivot."""

from fastapi import APIRouter
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import SessionDep
from nexctf.enums import SessionWindow
from nexctf.module.session import failed_logins_by_address, sessions_by_address
from nexctf.schema.user import (
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
