"""API-token scope enforcement and route-coverage guards."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi.openapi.utils import get_openapi
from fastapi.routing import iter_route_contexts
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.dep import _current_admin, _current_user, _optional_auth
from nexctf.api.openapi import (
    _annotate_scopes,
    _session_only_operations,
    flat_dependency_calls,
)
from nexctf.api.routes.sse import _user_channels
from nexctf.api.scope import (
    _PREFIX_GROUPS,
    VERB_OF_METHOD,
    _token_scopes,
    all_groups,
    build_table,
    grantable_scopes,
    group_for_path,
    register_plugin_prefix,
    reset_table,
    set_token_scopes,
)
from nexctf.api.security import create_api_token
from nexctf.core.config import settings
from nexctf.main import app
from nexctf.model import User, UserRole

from ..base import NULL_UUID

_AUTH_DEPS = {_current_user, _optional_auth, _current_admin}
# Route families deliberately outside every scope group.
UNGROUPED_PREFIXES = ("/auth/", "/oauth2/")


def _every_scope(*, admin: bool) -> list[str]:
    """Every scope the role may hold, which is as broad as a token now gets."""
    return sorted(grantable_scopes(admin))


# Grouped routes that take no auth dependency, so the scope check never runs.
_UNAUTHENTICATED_ROUTES = {
    "/api/v1/file/{uuid}/view",
    "/api/v1/info",
    "/api/v1/page",
    "/api/v1/page/{slug}",
    "/api/v1/plugins/manifest",
    "/api/v1/plugins/{plugin_key}/frontend/{file_path:path}",
    "/api/v1/stream/public",
}


def _v1_contexts() -> list[Any]:
    """Every versioned API route, as (context, group, dependency names)."""
    table = build_table(app)
    out = []
    for ctx in iter_route_contexts(app.routes):
        path = ctx.path or ""
        if not path.startswith(settings.API_V1_STR):
            continue
        out.append(
            (ctx, table.get(id(ctx.route)), flat_dependency_calls(ctx.dependant))
        )
    return out


def _is_ungrouped(path: str) -> bool:
    relative = path[len(settings.API_V1_STR) :]
    return relative.startswith(UNGROUPED_PREFIXES)


class TestRouteCoverage:
    def test_every_route_is_grouped_or_allowlisted(self) -> None:
        escaped = [
            ctx.path
            for ctx, group, _ in _v1_contexts()
            if group is None and not _is_ungrouped(ctx.path or "")
        ]
        assert not escaped, f"routes in no scope group: {escaped}"

    def test_authenticated_routes_reach_a_chokepoint(self) -> None:
        unauthenticated = {
            ctx.path
            for ctx, group, deps in _v1_contexts()
            if group is not None and not (deps & _AUTH_DEPS)
        }
        assert unauthenticated == _UNAUTHENTICATED_ROUTES

    def test_admin_group_iff_admin_gated(self) -> None:
        mismatched = [
            (ctx.path, group)
            for ctx, group, deps in _v1_contexts()
            if (group or "").startswith("admin.") != (_current_admin in deps)
        ]
        assert not mismatched, f"admin gate and scope group disagree: {mismatched}"

    def test_one_group_per_route_object(self) -> None:
        contexts = _v1_contexts()
        grouped = [ctx for ctx, group, _ in contexts if group is not None]
        assert len({id(ctx.route) for ctx in grouped}) == len(grouped)


class TestPublishedScopes:
    def _schema(self) -> dict:
        contexts = list(iter_route_contexts(app.routes))
        return _annotate_scopes(
            get_openapi(title="t", version="1", routes=contexts), contexts
        )

    def test_every_operation_publishes_its_scope(self) -> None:
        schema = self._schema()
        session_only = _session_only_operations(list(iter_route_contexts(app.routes)))
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                published = operation.get("x-token-scope")
                expected = group_for_path(path)
                if expected is None or (path, method) in session_only:
                    assert published is None
                    assert "browser session" in operation["description"]
                else:
                    verb = VERB_OF_METHOD[method.upper()]
                    assert published == f"{verb}:{expected}"
                    assert published in operation["description"]

    def test_a_session_only_operation_publishes_no_scope(self) -> None:
        """The docs must never advertise a scope the endpoint refuses to accept."""
        schema = self._schema()
        session_only = _session_only_operations(list(iter_route_contexts(app.routes)))
        assert session_only, "expected SessionOnlyDep to be in use"
        for path, method in session_only:
            operation = schema["paths"][path][method]
            assert "x-token-scope" not in operation
            assert "browser session" in operation["description"]

    def test_published_scope_matches_what_the_check_requires(self) -> None:
        """The docs and the request-time table are the same computation."""
        schema = self._schema()
        assert schema["paths"]["/api/v1/admin/team"]["post"]["x-token-scope"] == (
            "write:admin.team"
        )
        assert schema["paths"]["/api/v1/challenges"]["get"]["x-token-scope"] == (
            "read:challenge"
        )


class TestScopeMatching:
    def test_longest_prefix_wins(self) -> None:
        assert group_for_path("/api/v1/info") == "content"
        assert group_for_path("/api/v1/info/admin") == "admin.config"
        assert group_for_path("/api/v1/info/me") == "profile"
        assert group_for_path("/api/v1/me/profile") == "profile"
        assert group_for_path("/api/v1/me/tokens") == "token"
        assert group_for_path("/api/v1/custom-field") is None

    def test_plugin_prefixes_are_registered_at_mount(
        self, restore_prefix_groups
    ) -> None:
        register_plugin_prefix("/test-scope-plugin", "public")
        register_plugin_prefix("/test-scope-plugin", "admin")
        assert group_for_path("/api/v1/test-scope-plugin/x") == "plugin"
        assert group_for_path("/api/v1/admin/test-scope-plugin/x") == "admin.plugin"


class TestGrantableScopes:
    def test_every_group_is_grantable_in_both_verbs(self) -> None:
        granted = grantable_scopes(is_admin=True)
        for group in all_groups():
            assert f"read:{group}" in granted
            assert f"write:{group}" in granted

    def test_a_player_is_offered_no_admin_group(self) -> None:
        granted = grantable_scopes(is_admin=False)
        assert not [s for s in granted if s.split(":", 1)[1].startswith("admin.")]
        assert {"read:challenge", "write:challenge"} <= granted

    def test_no_scope_is_a_wildcard(self) -> None:
        for is_admin in (False, True):
            assert not [s for s in grantable_scopes(is_admin) if "*" in s]

    def test_a_plugin_group_is_grantable_before_any_plugin_mounts(self) -> None:
        assert {"read:plugin", "write:plugin"} <= grantable_scopes(is_admin=False)
        assert "write:admin.plugin" in grantable_scopes(is_admin=True)


@pytest.fixture
def restore_prefix_groups():
    """Undo writes to the module-level prefix map."""
    snapshot = dict(_PREFIX_GROUPS)
    yield
    _PREFIX_GROUPS.clear()
    _PREFIX_GROUPS.update(snapshot)


@pytest.fixture(autouse=True)
def fresh_scope_table():
    """Rebuild the memoised route table around each test."""
    reset_table()
    yield
    reset_table()


@pytest.fixture
def token_client(client_factory, db_session: AsyncSession, override_db_context):
    """Build a client authenticated by a bearer token with the given scopes."""

    @asynccontextmanager
    async def _make(
        role: UserRole, scopes: list[str]
    ) -> AsyncIterator[tuple[AsyncClient, User]]:
        user = User(username=f"scoped_{role.value}", role=role)
        db_session.add(user)
        await db_session.flush()
        raw, _ = await create_api_token(user.id, scopes=scopes)
        async with client_factory() as client:
            client.headers["Authorization"] = f"Bearer {raw}"
            yield client, user

    return _make


class TestTokenEnforcement:
    async def test_read_token_can_read_but_not_write(self, token_client) -> None:
        async with token_client(UserRole.user, ["read:challenge"]) as (c, _):
            assert (await c.get("/challenges")).status_code == 200
            resp = await c.post(f"/challenges/{NULL_UUID}/{NULL_UUID}/submit", json={})
            assert resp.status_code == 403

    async def test_every_player_scope_cannot_reach_admin(self, token_client) -> None:
        async with token_client(UserRole.admin, _every_scope(admin=False)) as (c, _):
            assert (await c.get("/admin/team")).status_code == 403
            assert (await c.get("/info/admin")).status_code == 403

    async def test_an_admin_scope_reaches_only_its_group(self, token_client) -> None:
        async with token_client(UserRole.admin, ["read:admin.team"]) as (c, _):
            assert (await c.get("/admin/team")).status_code == 200
            assert (await c.get("/challenges")).status_code == 403

    async def test_wrong_group_is_refused(self, token_client) -> None:
        async with token_client(UserRole.admin, ["read:admin.team"]) as (c, _):
            assert (await c.get("/admin/team")).status_code == 200
            assert (await c.get("/admin/user")).status_code == 403

    async def test_ungrouped_route_refuses_a_token(self, token_client) -> None:
        async with token_client(UserRole.user, _every_scope(admin=False)) as (c, _):
            assert (await c.get("/oauth2/client-info")).status_code == 403

    async def test_scope_failure_is_not_degraded_to_anonymous(
        self, token_client
    ) -> None:
        async with token_client(UserRole.user, ["read:admin.config"]) as (c, _):
            assert (await c.get("/challenges")).status_code == 403

    async def test_token_cannot_mint_a_token(self, token_client) -> None:
        async with token_client(UserRole.admin, _every_scope(admin=True)) as (c, _):
            assert (await c.get("/me/tokens")).status_code == 200
            assert (await c.post("/me/tokens", json={})).status_code == 403
            assert (await c.post("/me/password", json={})).status_code == 403
            assert (await c.post("/me/totp/setup")).status_code == 403

    async def test_a_token_can_revoke_a_token(self, token_client) -> None:
        """Revoking narrows, so it needs write:token, not a browser session."""
        async with token_client(UserRole.user, ["write:token"]) as (c, _):
            assert (await c.delete(f"/me/tokens/{NULL_UUID}")).status_code == 404

    async def test_revoking_needs_the_token_scope(self, token_client) -> None:
        async with token_client(UserRole.user, ["write:profile"]) as (c, _):
            assert (await c.delete(f"/me/tokens/{NULL_UUID}")).status_code == 403
            assert (await c.get("/me/tokens")).status_code == 403
            assert (await c.get("/me/profile")).status_code == 200

    def test_admin_event_stream_needs_the_admin_scope(self) -> None:
        admin = User(username="streamer", role=UserRole.admin)
        set_token_scopes(_every_scope(admin=False))
        assert "events:admin" not in _user_channels(admin)
        set_token_scopes(["read:admin.config"])
        assert "events:admin" in _user_channels(admin)
        _token_scopes.set(None)
        assert "events:admin" in _user_channels(admin)

    async def test_cookie_session_is_unscoped(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        assert (await c.get("/admin/team")).status_code == 200
        assert (await c.get("/challenges")).status_code == 200

    async def test_scopes_do_not_leak_into_a_later_cookie_request(
        self, token_client, admin_client: tuple[AsyncClient, User]
    ) -> None:
        """Scopes end with their request: a bearer call must not narrow a session."""
        async with token_client(UserRole.user, ["read:challenge"]) as (scoped, _):
            assert (await scoped.get("/challenges")).status_code == 200

        session, _ = admin_client
        assert (await session.get("/admin/team")).status_code == 200


class TestTokenCreation:
    async def test_non_admin_cannot_grant_admin_scopes(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        """The scope is real and an admin may grant it; this player may not."""
        c, _ = user_client
        assert "read:admin.team" in grantable_scopes(is_admin=True)
        resp = await c.post("/me/tokens", json={"scopes": ["read:admin.team"]})
        assert resp.status_code == 422

    async def test_grantable_scopes_are_role_filtered(
        self,
        user_client: tuple[AsyncClient, User],
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = user_client
        player = set((await c.get("/me/tokens/scopes")).json()["data"])
        assert player == grantable_scopes(is_admin=False)
        assert not [s for s in player if s.split(":", 1)[1].startswith("admin")]

        admin_c, _ = admin_client
        admin = set((await admin_c.get("/me/tokens/scopes")).json()["data"])
        assert admin == grantable_scopes(is_admin=True)
        assert player < admin

    async def test_an_explicit_group_is_accepted_and_enforced(
        self, user_client: tuple[AsyncClient, User], token_client
    ) -> None:
        c, _ = user_client
        resp = await c.post("/me/tokens", json={"scopes": ["read:challenge"]})
        assert resp.status_code == 201
        assert resp.json()["data"]["scopes"] == ["read:challenge"]
        async with token_client(UserRole.user, ["read:challenge"]) as (tc, _):
            assert (await tc.get("/challenges")).status_code == 200
            assert (await tc.get("/scoreboard")).status_code == 403

    async def test_a_write_grant_carries_its_read(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = user_client
        resp = await c.post("/me/tokens", json={"scopes": ["write:challenge"]})
        assert resp.status_code == 201
        assert resp.json()["data"]["scopes"] == ["read:challenge", "write:challenge"]

    async def test_an_empty_scope_list_is_refused(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = user_client
        assert (await c.post("/me/tokens", json={"scopes": []})).status_code == 422

    async def test_catalogue_offers_each_group(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        offered = (await c.get("/me/tokens/scopes")).json()["data"]
        assert offered == sorted(offered)
        assert {"read:challenge", "write:admin.team"} <= set(offered)

    async def test_scopes_must_be_named(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = user_client
        assert (await c.post("/me/tokens", json={"name": "t"})).status_code == 422

    async def test_an_unknown_scope_is_refused(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        for scope in ("read:*", "read:admin.*", "read:nonesuch", "sideways:team"):
            resp = await c.post("/me/tokens", json={"scopes": [scope]})
            assert resp.status_code == 422, scope
