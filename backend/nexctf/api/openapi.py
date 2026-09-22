"""OpenAPI schema and Swagger UI endpoint setup."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.routing import RouteContext, iter_route_contexts

from nexctf.api.dep import AdminAuthDep, _current_user, _optional_auth, _session_only
from nexctf.api.scope import VERB_OF_METHOD, group_for_path

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.dependencies.models import Dependant

_SESSION_ONLY_NOTE = (
    "**API tokens:** not accepted, this endpoint needs a browser session."
)
_PUBLIC_NOTE = "**Authentication:** none required, this endpoint is public."


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
            description = operation.get("description", "")
            operation["description"] = f"{description}\n\n{note}".lstrip()
    return schema


def setup_docs(app: FastAPI, admin_prefix: str) -> None:
    """Register filtered OpenAPI schemas and Swagger UI endpoints on *app*."""

    def _schema(title: str, prefix_filter: str, exclude: bool) -> dict[str, Any]:
        routes = [
            ctx
            for ctx in iter_route_contexts(app.routes)
            if (ctx.path or "").startswith(prefix_filter) != exclude
        ]
        return _annotate_scopes(
            get_openapi(title=title, version="1.0.0", routes=routes), routes
        )

    @app.get("/api/openapi.json", include_in_schema=False)
    def user_openapi() -> JSONResponse:
        return JSONResponse(_schema("NexCTF API", admin_prefix, exclude=True))

    @app.get(
        "/api/admin/openapi.json", include_in_schema=False, dependencies=[AdminAuthDep]
    )
    def admin_openapi() -> JSONResponse:
        return JSONResponse(_schema("NexCTF Admin API", admin_prefix, exclude=False))

    @app.get("/api/docs", include_in_schema=False)
    def user_docs():
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json", title="NexCTF – User API"
        )

    @app.get("/api/admin/docs", include_in_schema=False, dependencies=[AdminAuthDep])
    def admin_docs():
        return get_swagger_ui_html(
            openapi_url="/api/admin/openapi.json", title="NexCTF – Admin API"
        )
