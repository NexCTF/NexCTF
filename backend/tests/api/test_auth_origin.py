"""Anonymous auth posts refuse requests another site made the browser send."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from nexctf.core.config import settings

_LOGIN = {"username": "nobody", "password": "wrong-password"}
_CROSS_ORIGIN = "AUTH-403-CROSS-ORIGIN"


@pytest.fixture
def bare_client(http_client: AsyncClient) -> AsyncClient:
    """The anonymous client without the same-origin header it sends by default."""
    del http_client.headers["sec-fetch-site"]
    return http_client


async def _login(client: AsyncClient, headers: dict[str, str]):
    return await client.post("/auth/token", data=_LOGIN, headers=headers)


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://evil.example"},
        {"sec-fetch-site": "cross-site", "origin": "https://evil.example"},
        {"sec-fetch-site": "cross-site"},
        {"sec-fetch-site": "same-site", "origin": "https://sub.evil.example"},
        {"origin": "null"},
    ],
)
async def test_cross_site_login_is_refused(
    bare_client: AsyncClient, headers: dict[str, str]
) -> None:
    resp = await _login(bare_client, headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == _CROSS_ORIGIN


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"sec-fetch-site": "same-origin"},
        {"sec-fetch-site": "none"},
        {"sec-fetch-site": "cross-site", "origin": settings.all_cors_origins[-1]},
    ],
)
async def test_own_site_and_non_browser_logins_pass(
    bare_client: AsyncClient, headers: dict[str, str]
) -> None:
    resp = await _login(bare_client, headers)
    assert resp.status_code == 401


async def test_origin_matching_the_host_passes(bare_client: AsyncClient) -> None:
    resp = await _login(bare_client, {"origin": f"http://{bare_client.base_url.host}"})
    assert resp.status_code == 401


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/auth/register", {"username": "csrf", "password": "long-enough-pw"}),
        ("/auth/forgot-password", {"email": "a@example.com"}),
        ("/auth/resend-verification", {"email": "a@example.com"}),
        ("/auth/reset-password", {"token": "x", "new_password": "long-enough-pw"}),
        ("/auth/verify-email", {"token": "x"}),
    ],
)
async def test_every_anonymous_auth_post_is_covered(
    bare_client: AsyncClient, path: str, body: dict[str, str]
) -> None:
    resp = await bare_client.post(
        path, json=body, headers={"origin": "https://evil.example"}
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == _CROSS_ORIGIN


async def test_reads_are_not_checked(bare_client: AsyncClient) -> None:
    resp = await bare_client.get(
        "/auth/captcha/challenge", headers={"origin": "https://evil.example"}
    )
    assert resp.status_code != 403
