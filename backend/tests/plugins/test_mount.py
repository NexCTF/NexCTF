"""Plugin routers are mounted behind the auth their scope declares."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute, iter_route_contexts

from nexctf.api.dep import _current_admin, _current_user
from nexctf.api.openapi import flat_dependency_calls
from nexctf.plugins import RouterDef, mount_plugin_routes, routes


def _router() -> APIRouter:
    router = APIRouter()

    @router.get("/ping")
    async def ping() -> None: ...

    return router


@pytest.fixture
def mounted(isolated_plugins: None) -> dict[str, set]:
    """Mount one router per scope and return each route's dependency calls by path."""
    registry = routes.route_registry
    registry.add(RouterDef(_router(), "/p", scope="admin"), owner="demo")
    registry.add(RouterDef(_router(), "/p", scope="user"), owner="demo")
    registry.add(RouterDef(_router(), "/q", scope="anonymous"), owner="demo")
    app = FastAPI()
    mount_plugin_routes(app)
    return {
        ctx.path: set(flat_dependency_calls(ctx.dependant))
        for ctx in iter_route_contexts(app.routes)
        if ctx.path and isinstance(ctx.route, APIRoute)
    }


def test_admin_scope_requires_an_admin(mounted: dict[str, set]) -> None:
    assert _current_admin in mounted["/api/v1/admin/p/ping"]


def test_user_scope_requires_a_user(mounted: dict[str, set]) -> None:
    calls = mounted["/api/v1/p/ping"]
    assert _current_user in calls
    assert _current_admin not in calls


def test_anonymous_scope_adds_no_auth(mounted: dict[str, set]) -> None:
    assert not {_current_user, _current_admin} & mounted["/api/v1/q/ping"]
