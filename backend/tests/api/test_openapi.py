"""Guard the admin/public split of the generated OpenAPI schemas."""

from fastapi_toolsets.pytest import create_async_client

from nexctf.core.config import settings
from nexctf.main import app

_ADMIN_PREFIX = f"{settings.API_V1_STR}/admin"


async def test_schemas_are_split_on_the_admin_prefix() -> None:
    """The public schema must not leak admin routes, and vice versa."""
    async with create_async_client(app=app, base_url="http://127.0.0.1") as c:
        public = (await c.get("/api/openapi.json")).json()["paths"]
        admin = (await c.get("/api/admin/openapi.json")).json()["paths"]

    assert public and admin
    assert not [p for p in public if p.startswith(_ADMIN_PREFIX)]
    assert not [p for p in admin if not p.startswith(_ADMIN_PREFIX)]
