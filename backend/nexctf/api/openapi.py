"""OpenAPI schema and Swagger UI endpoint setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi import FastAPI


def setup_docs(app: "FastAPI", admin_prefix: str) -> None:
    """Register filtered OpenAPI schemas and Swagger UI endpoints on *app*."""

    def _schema(title: str, prefix_filter: str, exclude: bool) -> dict:
        routes = [
            r
            for r in app.routes
            if not hasattr(r, "path")
            or (
                not getattr(r, "path", "").startswith(prefix_filter)
                if exclude
                else getattr(r, "path", "").startswith(prefix_filter)
            )
        ]
        return get_openapi(title=title, version="1.0.0", routes=routes)

    @app.get("/api/openapi.json", include_in_schema=False)
    def user_openapi() -> JSONResponse:
        return JSONResponse(_schema("NexCTF API", admin_prefix, exclude=True))

    @app.get("/api/admin/openapi.json", include_in_schema=False)
    def admin_openapi() -> JSONResponse:
        return JSONResponse(_schema("NexCTF Admin API", admin_prefix, exclude=False))

    @app.get("/api/docs", include_in_schema=False)
    def user_docs():
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json", title="NexCTF – User API"
        )

    @app.get("/api/admin/docs", include_in_schema=False)
    def admin_docs():
        return get_swagger_ui_html(
            openapi_url="/api/admin/openapi.json", title="NexCTF – Admin API"
        )
