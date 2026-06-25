from fastapi import APIRouter
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import RedisDep
from nexctf.core.email import send_email
from nexctf.schema.email import AdminEmailTestRequest

email_router = APIRouter(prefix="/email", tags=["Email"])


@email_router.post("/test")
async def send_test_email(
    redis: RedisDep, obj: AdminEmailTestRequest
) -> Response[None]:
    await send_email(
        redis,
        obj.to,
        "NexCTF SMTP test",
        text="This is a test email confirming your NexCTF SMTP configuration works.",
    )
    return Response()
