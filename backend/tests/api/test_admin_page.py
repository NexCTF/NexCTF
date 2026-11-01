"""Custom page slugs: they become URL segments and bundle file names."""

import pytest
from httpx import AsyncClient

from nexctf.model import User


@pytest.mark.parametrize(
    ("slug", "status"),
    [("rules", 201), ("home_2", 201), ("../etc", 422), ("a/b", 422), ("-x", 422)],
)
async def test_slug_is_a_single_safe_segment(
    admin_client: tuple[AsyncClient, User], slug: str, status: int
) -> None:
    c, _ = admin_client
    resp = await c.post("/admin/page", json={"slug": slug, "title": "T"})
    assert resp.status_code == status, resp.text
