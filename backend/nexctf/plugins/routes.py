"""Registry of plugin-provided API routers."""

from __future__ import annotations

from nexctf.plugins.declare import RouterDef


class RouteRegistry:
    """Plugin routers waiting to be mounted, keyed on owner, scope and prefix."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], RouterDef] = {}

    def add(self, router: RouterDef, owner: str) -> None:
        """Record a router ``owner`` mounts at startup.

        Args:
            router: The router declaration.
            owner: The plugin key the router belongs to.
        """
        self._entries[(owner, router.scope, router.prefix)] = router

    def get_routers(self) -> list[RouterDef]:
        """Return every registered router."""
        return list(self._entries.values())

    def items(self) -> list[tuple[str, RouterDef]]:
        """Return every registered router with the plugin key that owns it."""
        return [(owner, router) for (owner, _, _), router in self._entries.items()]


route_registry = RouteRegistry()
