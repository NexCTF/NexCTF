"""Guard the admin/public split of the generated OpenAPI schemas."""

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi_toolsets.pytest import create_async_client
from httpx import AsyncClient

from nexctf.api import openapi
from nexctf.core.config import settings
from nexctf.main import app
from nexctf.model import User

_ADMIN_PREFIX = f"{settings.API_V1_STR}/admin"
# The doc routes sit at the app root, not under the clients' /api/v1 base_url.
_ROOT = "http://127.0.0.1"


async def test_schemas_are_split_on_the_admin_prefix(
    admin_client: tuple[AsyncClient, User],
) -> None:
    """The public schema must not leak admin routes, and vice versa."""
    c, _ = admin_client
    public = (await c.get(f"{_ROOT}/api/openapi.json")).json()["paths"]
    admin = (await c.get(f"{_ROOT}/api/admin/openapi.json")).json()["paths"]

    assert public and admin
    assert not [p for p in public if p.startswith(_ADMIN_PREFIX)]
    assert not [p for p in admin if not p.startswith(_ADMIN_PREFIX)]


async def test_admin_docs_reject_anonymous() -> None:
    """The admin schema and Swagger UI must not be readable without auth."""
    async with create_async_client(app=app, base_url=_ROOT) as c:
        assert (await c.get("/api/admin/openapi.json")).status_code == 401
        assert (await c.get("/api/admin/docs")).status_code == 401
        assert (await c.get("/api/openapi.json")).status_code == 200
        assert (await c.get("/api/docs")).status_code == 200


async def test_admin_docs_reject_regular_user(
    user_client: tuple[AsyncClient, User],
) -> None:
    """A logged-in non-admin must not reach the admin schema or Swagger UI."""
    c, _ = user_client
    assert (await c.get(f"{_ROOT}/api/admin/openapi.json")).status_code == 403
    assert (await c.get(f"{_ROOT}/api/admin/docs")).status_code == 403


async def test_optional_auth_operations_declare_their_security(
    admin_client: tuple[AsyncClient, User],
) -> None:
    """Optional-auth operations must publish a scheme, or Swagger sends no token."""
    from fastapi.routing import iter_route_contexts

    from nexctf.api.dep import _optional_auth
    from nexctf.api.openapi import flat_dependency_calls

    c, _ = admin_client
    paths = (await c.get(f"{_ROOT}/api/openapi.json")).json()["paths"]

    checked = 0
    for ctx in iter_route_contexts(app.routes):
        if _optional_auth not in flat_dependency_calls(ctx.dependant):
            continue
        for method in ctx.methods or ():
            operation = paths.get(ctx.path or "", {}).get(method.lower())
            if operation is None:
                continue
            assert operation.get("security"), f"{method} {ctx.path} declares no scheme"
            checked += 1

    assert checked, "no optional-auth operation found in the public schema"


async def test_reauth_gates_are_documented(
    admin_client: tuple[AsyncClient, User],
) -> None:
    """Operations behind the re-auth window say so, and whether tokens skip it."""
    c, _ = admin_client
    public = (await c.get(f"{_ROOT}/api/openapi.json")).json()["paths"]
    admin = (await c.get(f"{_ROOT}/api/admin/openapi.json")).json()["paths"]

    token_mint = public[f"{settings.API_V1_STR}/me/tokens"]["post"]["description"]
    user_delete = admin[f"{_ADMIN_PREFIX}/user/{{uuid}}"]["delete"]["description"]
    token_list = public[f"{settings.API_V1_STR}/me/tokens"]["get"]["description"]

    assert "AUTH-REAUTH-REQUIRED" in token_mint
    assert "API tokens skip this check" not in token_mint
    assert "API tokens skip this check" in user_delete
    assert "AUTH-REAUTH-REQUIRED" not in token_list


async def test_schema_is_built_once(monkeypatch) -> None:
    """Repeated anonymous requests must not regenerate the schema."""
    builds = 0
    build = openapi.get_openapi

    def _counting(**kwargs):
        nonlocal builds
        builds += 1
        return build(**kwargs)

    monkeypatch.setattr(openapi, "get_openapi", _counting)
    fresh = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    fresh.add_api_route("/api/v1/ping", lambda: {"ok": True})
    openapi.setup_docs(fresh, _ADMIN_PREFIX)

    async with create_async_client(app=fresh, base_url=_ROOT) as c:
        first = await c.get("/api/openapi.json")
        second = await c.get("/api/openapi.json")
    assert "/api/v1/ping" in first.json()["paths"]
    assert first.content == second.content
    assert builds == 1


class _Tags(HTMLParser):
    """Collects each start tag with its attributes, and any inline script text."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[tuple[str, dict[str, str]]] = []
        self.inline_script = ""
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.seen.append((tag, {name: value or "" for name, value in attrs}))
        self._in_script = tag == "script"

    def handle_endtag(self, tag: str) -> None:
        self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.inline_script += data.strip()


async def test_docs_page_pins_its_assets_and_runs_no_inline_script() -> None:
    async with create_async_client(app=app, base_url=_ROOT) as c:
        page = await c.get("/api/docs")
        init = await c.get("/api/docs/init.js")

    tags = _Tags()
    tags.feed(page.text)
    scripts = [attrs for tag, attrs in tags.seen if tag == "script"]
    assert [urlsplit(attrs["src"]).path for attrs in scripts][1] == "/api/docs/init.js"
    assert not tags.inline_script
    pinned = [*scripts[:1], *(attrs for tag, attrs in tags.seen if tag == "link")]
    assert len(scripts) == 2 and len(pinned) == 2
    for attrs in pinned:
        url = urlsplit(attrs.get("src") or attrs["href"])
        assert url.hostname == "cdn.jsdelivr.net"
        assert re.match(r"/npm/swagger-ui-dist@\d+\.\d+\.\d+/", url.path)
        assert attrs["integrity"].startswith("sha384-")
        assert attrs["crossorigin"] == "anonymous"

    policy = page.headers["content-security-policy"]
    assert "default-src 'none'" in policy
    assert "script-src 'self' https://cdn.jsdelivr.net;" in policy
    assert "frame-ancestors 'none'" in policy

    assert init.status_code == 200
    assert init.headers["content-type"].startswith("text/javascript")
    assert "SwaggerUIBundle(" in init.text
