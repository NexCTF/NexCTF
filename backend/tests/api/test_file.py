"""The public file redirect: inline only for images the browser cannot execute."""

from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import File


@pytest.mark.parametrize(
    ("mime_type", "disposition"),
    [("image/png", "inline"), ("text/html", "attachment"), (None, "attachment")],
)
async def test_view_is_inline_only_for_raster_images(
    http_client: AsyncClient,
    db_session: AsyncSession,
    mime_type: str | None,
    disposition: str,
) -> None:
    file = File(
        name="f",
        s3_key=f"files/{uuid4()}",
        original_filename="f.bin",
        mime_type=mime_type,
        is_public=True,
    )
    db_session.add(file)
    await db_session.flush()

    resp = await http_client.get(f"/file/{file.id}/view", follow_redirects=False)

    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["response-content-disposition"][0].startswith(disposition)
