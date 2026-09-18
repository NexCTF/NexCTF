"""Permission scopes for API tokens."""

from __future__ import annotations

from collections.abc import Iterable
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute, iter_route_contexts

from nexctf.core.config import settings
from nexctf.exceptions import InsufficientScopeError, UnscopableEndpointError

VERB_OF_METHOD = {
    "GET": "read",
    "HEAD": "read",
    "OPTIONS": "read",
    "POST": "write",
    "PUT": "write",
    "PATCH": "write",
    "DELETE": "write",
}
_PREFIX_GROUPS: dict[str, str] = {
    "/admin/backup": "admin.backup",
    "/admin/challenge": "admin.challenge",
    "/admin/question": "admin.challenge",
    "/admin/solution": "admin.challenge",
    "/admin/hint": "admin.challenge",
    "/admin/submission": "admin.challenge",
    "/admin/score-adjustment": "admin.challenge",
    "/admin/file": "admin.challenge",
    "/admin/scoreboard": "admin.scoreboard",
    "/admin/stats": "admin.scoreboard",
    "/admin/team": "admin.team",
    "/admin/user": "admin.user",
    "/admin/session": "admin.user",
    "/admin/custom-field": "admin.user",
    "/admin/notification": "admin.notification",
    "/admin/email": "admin.notification",
    "/admin/page": "admin.content",
    "/admin/link": "admin.content",
    "/admin/config": "admin.config",
    "/admin/event": "admin.config",
    "/admin/scheduler": "admin.config",
    "/admin/feedback": "admin.config",
    "/admin/oauth-provider": "admin.config",
    "/admin/oauth-client": "admin.config",
    "/admin/plugins": "admin.config",
    "/info/admin": "admin.config",
    "/info/me": "profile",
    "/challenges": "challenge",
    "/file": "challenge",
    "/scoreboard": "scoreboard",
    "/team": "team",
    "/me/tokens": "token",
    "/me": "profile",
    "/notification": "notification",
    "/stream": "notification",
    "/info": "content",
    "/page": "content",
    "/plugins": "content",
}
_PLUGIN_GROUPS = frozenset({"plugin", "admin.plugin"})
# The admin audit channel rides the notification group, so it gates on its own scope.
ADMIN_EVENTS_SCOPE = "read:admin.config"

_token_scopes: ContextVar[frozenset[str] | None] = ContextVar(
    "token_scopes", default=None
)

_table: dict[int, str] | None = None


def set_token_scopes(scopes: list[str]) -> None:
    """Bind the authenticating token's scopes for the current request."""
    _token_scopes.set(frozenset(scopes))


def current_token_scopes() -> frozenset[str] | None:
    """Return the request's token scopes, or None for a cookie session."""
    return _token_scopes.get()


def register_plugin_prefix(prefix: str, scope: str) -> None:
    """Map a plugin router's mount prefix to its plugin group."""
    if scope == "admin":
        _PREFIX_GROUPS[f"/admin{prefix}"] = "admin.plugin"
    else:
        _PREFIX_GROUPS[prefix] = "plugin"


def all_groups() -> frozenset[str]:
    """Every group in the scope vocabulary, plugin groups included."""
    return frozenset(_PREFIX_GROUPS.values()) | _PLUGIN_GROUPS


def grantable_scopes(is_admin: bool) -> frozenset[str]:
    """Every scope a token may be granted, narrowed to the caller's families."""
    groups = all_groups()
    if not is_admin:
        groups = frozenset(g for g in groups if not g.startswith("admin."))
    return frozenset(
        f"{verb}:{group}" for verb in ("read", "write") for group in groups
    )


def with_implied_reads(scopes: Iterable[str]) -> list[str]:
    """Sorted scopes where every write grant carries its read counterpart."""
    granted = set(scopes)
    granted |= {f"read:{s.split(':', 1)[1]}" for s in granted if s.startswith("write:")}
    return sorted(granted)


def group_for_path(path: str) -> str | None:
    """Return the group owning *path*, or None when it is in no group."""
    if not path.startswith(settings.API_V1_STR):
        return None
    relative = path[len(settings.API_V1_STR) :]
    match = max(
        (p for p in _PREFIX_GROUPS if relative.startswith(p)), key=len, default=None
    )
    return _PREFIX_GROUPS[match] if match is not None else None


def build_table(app: FastAPI) -> dict[int, str]:
    """Map the identity of every grouped route to its group."""
    table: dict[int, str] = {}
    for ctx in iter_route_contexts(app.routes):
        group = group_for_path(ctx.path or "")
        if group is not None and isinstance(ctx.route, APIRoute):
            table[id(ctx.route)] = group
    return table


def reset_table() -> None:
    """Drop the memoised route table so the next check rebuilds it."""
    global _table
    _table = None


def _get_table(app: FastAPI) -> dict[int, str]:
    global _table
    if _table is None:
        _table = build_table(app)
    return _table


def enforce_token_scope(request: Request) -> None:
    """Raise unless the request's token may reach this route. No-op for sessions."""
    granted = current_token_scopes()
    if granted is None:
        return
    group = _get_table(request.app).get(id(request.scope.get("route")))
    verb = VERB_OF_METHOD.get(request.method)
    if group is None or verb is None:
        raise UnscopableEndpointError()
    required = f"{verb}:{group}"
    if required not in granted:
        raise InsufficientScopeError(required)
