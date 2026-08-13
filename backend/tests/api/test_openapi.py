"""Guard the admin/public split of the generated OpenAPI schemas."""

from fastapi_toolsets.pytest import create_async_client
from httpx import AsyncClient

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
