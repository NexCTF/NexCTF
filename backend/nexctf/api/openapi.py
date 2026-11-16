"""OpenAPI schema and Swagger UI endpoint setup."""

from __future__ import annotations

import functools
from collections.abc import Callable
from html import escape
from typing import TYPE_CHECKING, Any

from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.routing import RouteContext, iter_route_contexts

from nexctf.api.dep import (
    AdminAuthDep,
    _current_user,
    _fresh_session,
    _fresh_unless_token,
    _optional_auth,
    _session_only,
)
from nexctf.api.scope import VERB_OF_METHOD, group_for_path
from nexctf.api.security import REAUTH_WINDOW

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.dependencies.models import Dependant

_SESSION_ONLY_NOTE = (
    "**API tokens:** not accepted, this endpoint needs a browser session."
)
_PUBLIC_NOTE = "**Authentication:** none required, this endpoint is public."
_FRESH_SESSION_NOTE = (
    "**Re-authentication:** the session must have signed in within the last "
    f"{REAUTH_WINDOW // 60} minutes, else `AUTH-REAUTH-REQUIRED`; "
    "renew it with `POST /auth/reauth`."
)
_TOKENS_SKIP = " API tokens skip this check."

_SWAGGER_CDN = "https://cdn.jsdelivr.net"
_SWAGGER_DIST = f"{_SWAGGER_CDN}/npm/swagger-ui-dist@5.34.1"
_SWAGGER_JS_SRI = (
    "sha384-XFYN47VzPiDY6qPtxYKg0nqUeW/upo20xf1j2SUE7gT/i35FJB4cuS/71Iegzk8Z"
)
_SWAGGER_CSS_SRI = (
    "sha384-4c3vsE5f+trhFyHrFrLM1fFGUn531NIaC7dcqEWIJdoRQJ5CkJbSuSCwXLpaS1KF"
)
_DOCS_INIT_PATH = "/api/docs/init.js"
_DOCS_CSP = (
    "default-src 'none'; "
    f"script-src 'self' {_SWAGGER_CDN}; "
    f"style-src {_SWAGGER_CDN} 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
_DOCS_PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<link rel="stylesheet" href="{_SWAGGER_DIST}/swagger-ui.css"
  integrity="{_SWAGGER_CSS_SRI}" crossorigin="anonymous">
</head>
<body>
<div id="swagger-ui" data-openapi-url="{{openapi_url}}"></div>
<script src="{_SWAGGER_DIST}/swagger-ui-bundle.js"
  integrity="{_SWAGGER_JS_SRI}" crossorigin="anonymous"></script>
<script src="{_DOCS_INIT_PATH}"></script>
</body>
</html>
"""
_DOCS_INIT = """const root = document.getElementById("swagger-ui");
window.ui = SwaggerUIBundle({
  url: root.dataset.openapiUrl,
  dom_id: "#swagger-ui",
  layout: "BaseLayout",
  deepLinking: true,
  showExtensions: true,
  showCommonExtensions: true,
  presets: [
    SwaggerUIBundle.presets.apis,
    SwaggerUIBundle.SwaggerUIStandalonePreset,
  ],
});
"""


def _docs_page(*, openapi_url: str, title: str) -> HTMLResponse:
    """Swagger UI for *openapi_url*: pinned assets and no inline script."""
    page = _DOCS_PAGE.format(
        title=escape(title), openapi_url=escape(openapi_url, quote=True)
    )
    return HTMLResponse(page, headers={"Content-Security-Policy": _DOCS_CSP})


def flat_dependency_calls(dependant: Dependant) -> set[Callable[..., Any]]:
    """Every dependency callable reachable from *dependant*."""
    calls: set[Callable[..., Any]] = set()
    for sub in dependant.dependencies:
        if sub.call is not None:
            calls.add(sub.call)
        calls |= flat_dependency_calls(sub)
    return calls


def _operations_reaching(
    contexts: list[RouteContext], *calls: Callable[..., Any]
) -> set[tuple[str, str]]:
    """The ``(path, method)`` pairs whose dependency graph includes any of *calls*."""
    return {
        (ctx.path or "", method.lower())
        for ctx in contexts
        if flat_dependency_calls(ctx.dependant).intersection(calls)
        for method in ctx.methods or ()
    }


def _session_only_operations(contexts: list[RouteContext]) -> set[tuple[str, str]]:
    """The ``(path, method)`` pairs that refuse bearer auth outright."""
    return _operations_reaching(contexts, _session_only)


def _authenticated_operations(contexts: list[RouteContext]) -> set[tuple[str, str]]:
    """The ``(path, method)`` pairs that authenticate the caller, token or session."""
    return _operations_reaching(contexts, _current_user, _optional_auth)


def _annotate_scopes(
    schema: dict[str, Any], contexts: list[RouteContext]
) -> dict[str, Any]:
    """Publish each operation's required token scope, in the body and the docs."""
    session_only = _session_only_operations(contexts)
    authenticated = _authenticated_operations(contexts)
    fresh = _operations_reaching(contexts, _fresh_session, _fresh_unless_token)
    for path, operations in schema.get("paths", {}).items():
        group = group_for_path(path)
        for method, operation in operations.items():
            verb = VERB_OF_METHOD.get(method.upper())
            if group is None or verb is None or (path, method) in session_only:
                note = _SESSION_ONLY_NOTE
            elif (path, method) not in authenticated:
                note = _PUBLIC_NOTE
            else:
                scope = f"{verb}:{group}"
                operation["x-token-scope"] = scope
                note = f"**Required token scope:** `{scope}`"
            if (path, method) in fresh:
                skip = "" if (path, method) in session_only else _TOKENS_SKIP
                note = f"{note}\n\n{_FRESH_SESSION_NOTE}{skip}"
            description = operation.get("description", "")
            operation["description"] = f"{description}\n\n{note}".lstrip()
    return schema


def setup_docs(app: FastAPI, admin_prefix: str) -> None:
    """Register filtered OpenAPI schemas and Swagger UI endpoints on *app*."""

    @functools.cache
    def _schema_body(admin: bool) -> bytes:
        """The admin or public schema, rendered on first use and then kept."""
        routes = [
            ctx
            for ctx in iter_route_contexts(app.routes)
            if (ctx.path or "").startswith(admin_prefix) == admin
        ]
        title = "NexCTF Admin API" if admin else "NexCTF API"
        schema = _annotate_scopes(
            get_openapi(title=title, version="1.0.0", routes=routes), routes
        )
        return bytes(JSONResponse(schema).body)

    def _schema(*, admin: bool) -> Response:
        return Response(_schema_body(admin), media_type="application/json")

    @app.get("/api/openapi.json", include_in_schema=False)
    def user_openapi() -> Response:
        return _schema(admin=False)

    @app.get(
        "/api/admin/openapi.json", include_in_schema=False, dependencies=[AdminAuthDep]
    )
    def admin_openapi() -> Response:
        return _schema(admin=True)

    @app.get(_DOCS_INIT_PATH, include_in_schema=False)
    def docs_init() -> Response:
        return Response(_DOCS_INIT, media_type="text/javascript")

    @app.get("/api/docs", include_in_schema=False)
    def user_docs() -> HTMLResponse:
        return _docs_page(openapi_url="/api/openapi.json", title="NexCTF – User API")

    @app.get("/api/admin/docs", include_in_schema=False, dependencies=[AdminAuthDep])
    def admin_docs() -> HTMLResponse:
        return _docs_page(
            openapi_url="/api/admin/openapi.json", title="NexCTF – Admin API"
        )
