"""Plugin discovery, loading, and FastAPI wiring."""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
import re
import sys
from dataclasses import dataclass
from email.utils import getaddresses
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "nexctf.plugins"
_BUILTINS = {
    "challenge": "nexctf.plugins.builtin.challenge",
    "solution": "nexctf.plugins.builtin.solution",
}

_loaded: dict[str, ModuleType] = {}
_plugin_tables: set[str] = set()
_plugin_metadata: dict[str, PluginMeta] = {}
_plugin_migrations: dict[str, tuple[Path, frozenset[str]]] = {}


@dataclass
class PluginMeta:
    """Metadata describing a single loaded (or failed) plugin."""

    key: str
    name: str
    display_name: str
    version: str | None
    description: str | None
    authors: list[str]
    repo_url: str | None
    homepage_url: str | None
    is_builtin: bool
    is_active: bool = True
    load_error: str | None = None


def plugin_key(dist_name: str) -> str:
    """Normalise a distribution name into the key a plugin is tracked under.

    Args:
        dist_name: The installed distribution name, e.g. ``"nexctf-sandbox"``.

    Returns:
        The normalised key, e.g. ``"nexctf_sandbox"``.
    """
    return re.sub(r"[-_.]+", "_", dist_name).lower()


def version_table(key: str) -> str:
    """Return the Alembic version table a plugin's migrations are tracked in.

    Args:
        key: The plugin key, as returned by :func:`plugin_key`.

    Returns:
        The version table name, e.g. ``"alembic_version_nexctf_sandbox"``.
    """
    return f"alembic_version_{key}"


def _display_name(dist_name: str) -> str:
    """Derive a human-readable name from a distribution name."""
    stem = re.sub(r"^nexctf[-_](plugin[-_])?", "", dist_name, flags=re.IGNORECASE)
    return re.sub(r"[-_.]+", " ", stem).title() or dist_name


def _authors(metadata) -> list[str]:
    """Collect author names from ``Author`` and ``Author-email`` headers."""
    names = [a.strip() for a in metadata.get_all("Author") or [] if a.strip()]
    names += [n for n, _ in getaddresses(metadata.get_all("Author-email") or []) if n]
    return list(dict.fromkeys(names))


def _project_urls(metadata) -> dict[str, str]:
    """Parse ``Project-URL`` headers into a lowercased label → URL mapping."""
    urls = {}
    for raw in metadata.get_all("Project-URL") or []:
        label, _, url = raw.partition(",")
        urls[label.strip().lower()] = url.strip()
    return urls


def _builtin_metadata(key: str) -> PluginMeta:
    """Build metadata for an in-tree builtin from the nexctf distribution."""
    try:
        meta = _installed_metadata(key, importlib.metadata.distribution("nexctf"))
    except importlib.metadata.PackageNotFoundError:
        meta = PluginMeta(
            key=key,
            name=key,
            display_name=key,
            version=None,
            description=None,
            authors=[],
            repo_url=None,
            homepage_url=None,
            is_builtin=True,
        )
    meta.name = f"nexctf-plugin-{key}"
    meta.display_name = _display_name(key)
    meta.description = f"Built-in {key} types for NexCTF"
    meta.is_builtin = True
    return meta


def _installed_metadata(
    key: str,
    dist: importlib.metadata.Distribution,
    *,
    is_active: bool = True,
    load_error: str | None = None,
) -> PluginMeta:
    """Build metadata for an installed plugin from its distribution metadata.

    Args:
        key: The plugin key the distribution is tracked under.
        dist: The installed distribution providing the entry point.
        is_active: Whether the plugin loaded successfully.
        load_error: Error message captured when loading failed, if any.

    Returns:
        The assembled metadata.
    """
    metadata = dist.metadata
    urls = _project_urls(metadata)
    return PluginMeta(
        key=key,
        name=metadata["Name"] or key,
        display_name=_display_name(metadata["Name"] or key),
        version=metadata["Version"],
        description=metadata["Summary"],
        authors=_authors(metadata),
        repo_url=urls.get("repository") or urls.get("source"),
        homepage_url=urls.get("homepage"),
        is_builtin=False,
        is_active=is_active,
        load_error=load_error,
    )


def derive_owned_tables(package: str) -> frozenset[str]:
    """Derive the table names a plugin owns from its mapped models.

    Args:
        package: The plugin's root package name, e.g. ``"nexctf_sandbox"``.

    Returns:
        The set of table names declared by models inside that package.
    """
    from sqlalchemy import Table

    from nexctf.model import Base

    prefix = f"{package}."
    return frozenset(
        mapper.local_table.name
        for mapper in Base.registry.mappers
        if f"{mapper.class_.__module__}.".startswith(prefix)
        and isinstance(mapper.local_table, Table)
    )


def get_plugin_tables() -> frozenset[str]:
    """Return the set of table names owned by plugins.

    Returns:
        An immutable view of the registered plugin table names.
    """
    return frozenset(_plugin_tables)


def get_plugin_metadata() -> dict[str, PluginMeta]:
    """Return metadata for all loaded plugins.

    Returns:
        A mapping of plugin key to :class:`PluginMeta`.
    """
    return _plugin_metadata


def get_plugin_migrations() -> dict[str, tuple[Path, frozenset[str]]]:
    """Return the migrations of every loaded plugin that ships some.

    Returns:
        A mapping of plugin key to its ``(versions directory, owned tables)``.
    """
    return _plugin_migrations


def load_builtin_plugins() -> None:
    """Import the in-tree builtin plugins and register their types."""
    for key, module_path in _BUILTINS.items():
        if key in _loaded:
            continue
        logger.debug("plugin.load name=%s module=%s builtin=true", key, module_path)
        _loaded[key] = importlib.import_module(module_path)
        _plugin_metadata[key] = _builtin_metadata(key)


def _load_installed_plugins() -> None:
    """Import every installed distribution declaring a ``nexctf.plugins`` entry point."""
    for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
        if ep.dist is None:
            continue
        key = plugin_key(ep.dist.name)
        if key in _loaded or key in _plugin_metadata:
            continue
        try:
            logger.debug("plugin.load name=%s module=%s", key, ep.module)
            _loaded[key] = importlib.import_module(ep.module)
            _plugin_metadata[key] = _installed_metadata(key, ep.dist)
            # Resolve from the root package, not the entry-point module, so an
            # entry point aimed at a submodule still finds models and migrations.
            root = ep.module.split(".")[0]
            owned = derive_owned_tables(root)
            _plugin_tables.update(owned)
            versions = (
                Path(sys.modules[root].__file__ or "").parent / "alembic" / "versions"
            )
            if versions.is_dir():
                _plugin_migrations[key] = (versions, owned)
        except Exception as exc:
            logger.exception("plugin.load_failed name=%s", key)
            _plugin_metadata[key] = _installed_metadata(
                key, ep.dist, is_active=False, load_error=str(exc)
            )


def load_plugin_registries() -> None:
    """Populate the plugin registries by importing builtin and installed plugins."""
    load_builtin_plugins()
    _load_installed_plugins()


def _patch_crud_classes() -> None:
    """Patch base CRUD classes with plugin-registered load options."""
    from nexctf.crud import ChallengeCrud, SolutionCrud
    from nexctf.plugins.registry import challenge_registry, solution_registry

    challenge_registry.apply(ChallengeCrud)
    solution_registry.apply(SolutionCrud)


def mount_plugin_routes(app: FastAPI) -> None:
    """Mount plugin-registered routers onto the FastAPI app.

    Args:
        app: The FastAPI application to mount the routers on.
    """
    from fastapi import APIRouter

    from nexctf.api.dep import AdminAuthDep
    from nexctf.core.config import settings
    from nexctf.plugins.routes import route_registry

    _admin = APIRouter(
        prefix=f"{settings.API_V1_STR}/admin",
        dependencies=[AdminAuthDep],
    )
    _public = APIRouter(prefix=settings.API_V1_STR)

    for r, prefix, tags in route_registry.get_routers(scope="admin"):
        _admin.include_router(r, prefix=prefix, tags=tags)
    for r, prefix, tags in route_registry.get_routers(scope="public"):
        _public.include_router(r, prefix=prefix, tags=tags)

    app.include_router(_admin)
    app.include_router(_public)


async def init_plugins(app: FastAPI, session: AsyncSession) -> None:
    """Load all plugins, patch CRUD classes, reconcile configs, and mount routes.

    Args:
        app: The FastAPI application to wire plugin routes into.
        session: An open async database session.
    """
    from nexctf.core.appconfig import sync_to_redis
    from nexctf.core.cache import get_client as get_redis_client

    load_plugin_registries()
    _patch_crud_classes()
    await sync_to_redis(session, get_redis_client())
    mount_plugin_routes(app)
