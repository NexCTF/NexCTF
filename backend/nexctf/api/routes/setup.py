"""First-run setup: create the first admin with the console setup token."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response as RawResponse
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import RedisDep, SessionDep, bind_setup_audit_context
from nexctf.api.security import issue_session_cookie
from nexctf.core.logging import bind_user_context
from nexctf.core.rate_limit import check_rate_limit, client_rate_key
from nexctf.module.setup import admin_exists, create_first_admin
from nexctf.schema.setup import SetupAdminCreate, SetupStatusRead

setup_router = APIRouter(
    prefix="/setup", tags=["setup"], dependencies=[Depends(bind_setup_audit_context)]
)


@setup_router.get("")
async def setup_status(session: SessionDep) -> Response[SetupStatusRead]:
    """Whether the instance still waits for its first admin."""
    return Response(
        data=SetupStatusRead(admin_required=not await admin_exists(session))
    )


@setup_router.post("/admin", status_code=204)
async def first_admin(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    response: RawResponse,
    body: SetupAdminCreate,
) -> None:
    """Create the first admin with the setup token and sign them in."""
    await check_rate_limit(
        redis,
        client_rate_key("setup", request),
        name="setup",
        window_seconds=60,
        max_requests=5,
    )
    user = await create_first_admin(session, redis, body)
    await issue_session_cookie(session, response, user, request)
    bind_user_context(user.id, user.username)
