"""Admin file uploads: streamed to S3 and refused past the size limit."""

import pytest
from httpx import AsyncClient

from nexctf.core import s3
from nexctf.core.config import settings
from nexctf.model import User


async def test_upload_lands_in_s3_with_its_size(
    admin_client: tuple[AsyncClient, User],
) -> None:
    c, _ = admin_client
    resp = await c.post(
        "/admin/file",
        data={"name": "notes"},
        files={"upload": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["file_size"] == 11
    assert await s3.download(data["s3_key"]) == b"hello world"
    await s3.delete(data["s3_key"])


async def test_upload_over_the_limit_is_refused(
    admin_client: tuple[AsyncClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 4)
    c, _ = admin_client
    resp = await c.post(
        "/admin/file",
        data={"name": "big"},
        files={"upload": ("big.bin", b"0123456789", "application/octet-stream")},
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "FILE-413"
