"""Registry of plugin-provided API routers."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from fastapi import APIRouter

type RouterScope = Literal["admin", "public"]
type TagList = list[str | Enum]


class RouteRegistry:
    """Standalone registry for plugin-provided API routes."""

    def __init__(self) -> None:
        self._entries: list[tuple[APIRouter, str, TagList, RouterScope]] = []

    def register(
        self,
        router: APIRouter,
        prefix: str,
        scope: RouterScope = "admin",
        tags: TagList | None = None,
    ) -> None:
        """Register a plugin router to be mounted at startup.

        Args:
            router: The APIRouter to mount.
            prefix: Path prefix the router is mounted under.
            scope: Whether the router is admin-only or public.
            tags: OpenAPI tags applied to the router's routes.
        """
        self._entries.append((router, prefix, list(tags or []), scope))

    def get_routers(
        self, scope: RouterScope | None = None
    ) -> list[tuple[APIRouter, str, TagList]]:
        """Return the registered routers, optionally filtered by scope.

        Args:
            scope: Only return routers with this scope, or ``None`` for all.

        Returns:
            A list of ``(router, prefix, tags)`` tuples.
        """
        return [
            (r, prefix, tags)
            for r, prefix, tags, s in self._entries
            if scope is None or s == scope
        ]


route_registry = RouteRegistry()
