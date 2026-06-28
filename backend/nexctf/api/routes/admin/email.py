from fastapi import APIRouter
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import RedisDep, SessionDep
from nexctf.core.email import send_email
from nexctf.module.audit import audit_actor
from nexctf.module.events import emit
from nexctf.schema.email import AdminEmailTestRequest

email_router = APIRouter(prefix="/email", tags=["Email"])


@email_router.post("/test")
async def send_test_email(
    session: SessionDep, redis: RedisDep, obj: AdminEmailTestRequest
) -> Response[None]:
    await send_email(
        redis,
        obj.to,
        "NexCTF SMTP test",
        text="This is a test email confirming your NexCTF SMTP configuration works.",
    )
    actor_id, ip = audit_actor()
    await emit(
        session,
        redis,
        event_type="admin.email_test",
        actor_id=actor_id,
        ip=ip,
        meta={"to": obj.to},
    )
    return Response()
