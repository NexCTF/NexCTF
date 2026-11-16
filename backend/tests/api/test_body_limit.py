"""Request bodies are capped, with the large limit kept for admin uploads."""

from httpx import AsyncClient

from nexctf.core.config import settings
from nexctf.model import User

_OVERSIZED = b"x" * (settings.MAX_BODY_BYTES + 1)


async def test_anonymous_oversized_body_is_refused(http_client: AsyncClient) -> None:
    resp = await http_client.post(
        "/auth/token", content=_OVERSIZED, headers={"content-type": "text/plain"}
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "REQ-413"


async def test_oversized_body_without_length_is_refused(
    http_client: AsyncClient,
) -> None:
    async def chunks():
        yield _OVERSIZED[: len(_OVERSIZED) // 2]
        yield _OVERSIZED[len(_OVERSIZED) // 2 :]

    resp = await http_client.post(
        "/auth/register",
        content=chunks(),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "REQ-413"


async def test_admin_upload_keeps_the_large_limit(
    admin_client: tuple[AsyncClient, User],
) -> None:
    c, _ = admin_client
    resp = await c.post(
        "/admin/file",
        data={"name": "large"},
        files={"upload": ("large.bin", _OVERSIZED, "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
