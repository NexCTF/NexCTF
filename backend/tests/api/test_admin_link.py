"""Navbar links only take web or mail addresses."""

import pytest
from httpx import AsyncClient

from nexctf.model import User


@pytest.mark.parametrize(
    ("url", "status"),
    [
        ("https://discord.gg/x", 201),
        ("mailto:orga@example.com", 201),
        ("javascript:alert(1)", 422),
        ("javascript://host/%0aalert(1)", 422),
        ("data:text/html,x", 422),
    ],
)
async def test_link_url_scheme(
    admin_client: tuple[AsyncClient, User], url: str, status: int
) -> None:
    c, _ = admin_client
    resp = await c.post(
        "/admin/link", json={"name": "L", "url": url, "visibility": "public"}
    )
    assert resp.status_code == status, resp.text
