"""Plugin discovery, loading, and FastAPI wiring."""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
import os
import re
from dataclasses import dataclass, replace
from email.utils import getaddresses
from pathlib import Path
from typing import TYPE_CHECKING, get_args

from nexctf.plugins.config import plugin_config_defs, register_config
from nexctf.plugins.declare import (
    NavSection,
    PageDef,
    Plugin,
    RouterDef,
    RouterScope,
)
from nexctf.plugins.frontend import frontend_registry
from nexctf.plugins.registry import (
    challenge_registry,
    scheduler_registry,
    solution_registry,
)
from nexctf.plugins.routes import route_registry

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexctf.core.appconfig import ConfigDef

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "nexctf.plugins"
_DISABLED_ENV = "NEXCTF_DISABLED_PLUGINS"
_BUILTINS = {
    "challenge": "nexctf.plugins.builtin.challenge",
    "solution": "nexctf.plugins.builtin.solution",
}
_CORE_KEY = "core"
_CORE_MODULES = ("nexctf.module.scheduler",)

_ROUTER_SCOPES: tuple[str, ...] = get_args(RouterScope.__value__)
_PREFIX_RE = re.compile(r"(/[a-z0-9][a-z0-9_-]*)+")
_NAV_SECTIONS: tuple[str, ...] = get_args(NavSection.__value__)
_PAGE_PATH_RE = re.compile(r"([a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*)?")

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
    is_disabled: bool = False
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
    """Return the Alembic version table a plugin's migrations are tracked in."""
    return f"alembic_version_{key}"


def _display_name(dist_name: str) -> str:
    """Derive a human-readable name from a distribution name."""
    stem = re.sub(r"^nexctf[-_](plugin[-_])?", "", dist_name, flags=re.IGNORECASE)
    return re.sub(r"[-_.]+", " ", stem).title() or dist_name


def _authors(dist: importlib.metadata.Distribution) -> list[str]:
    """Collect author names from ``Author`` and ``Author-email`` headers."""
    metadata = dist.metadata
    names = [a.strip() for a in metadata.get_all("Author") or [] if a.strip()]
    names += [n for n, _ in getaddresses(metadata.get_all("Author-email") or []) if n]
    return list(dict.fromkeys(names))


def _project_urls(dist: importlib.metadata.Distribution) -> dict[str, str]:
    """Parse ``Project-URL`` headers into a lowercased label → URL mapping."""
    urls = {}
    for raw in dist.metadata.get_all("Project-URL") or []:
        label, _, url = raw.partition(",")
        urls[label.strip().lower()] = url.strip()
    return urls


def _builtin_metadata(key: str) -> PluginMeta:
    """Build metadata for an in-tree builtin, borrowing the nexctf distribution's."""
    return replace(
        _installed_metadata(key, importlib.metadata.distribution("nexctf")),
        display_name=_display_name(key),
        description=f"Built-in {key} types for NexCTF",
        is_builtin=True,
    )


def _installed_metadata(
    key: str,
    dist: importlib.metadata.Distribution,
    *,
    is_active: bool = True,
    is_disabled: bool = False,
    load_error: str | None = None,
) -> PluginMeta:
    """Build metadata for an installed plugin from its distribution metadata.

    Args:
        key: The plugin key the distribution is tracked under.
        dist: The installed distribution providing the entry point.
        is_active: Whether the plugin loaded successfully.
        is_disabled: Whether the operator disabled the plugin.
        load_error: Error message captured when loading failed, if any.

    Returns:
        The assembled metadata.
    """
    metadata = dist.metadata
    urls = _project_urls(dist)
    return PluginMeta(
        key=key,
        name=metadata["Name"] or key,
        display_name=_display_name(metadata["Name"] or key),
        version=metadata["Version"],
        description=metadata["Summary"],
        authors=_authors(dist),
        repo_url=urls.get("repository") or urls.get("source"),
        homepage_url=urls.get("homepage"),
        is_builtin=False,
        is_active=is_active,
        is_disabled=is_disabled,
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


def _validate_routers(routers: list[RouterDef]) -> None:
    """Raise if a router has an unknown scope or a malformed or taken prefix."""
    from nexctf.api.scope import plugin_prefix_conflict

    for router in routers:
        if router.scope not in _ROUTER_SCOPES:
            raise ValueError(
                f"router {router.prefix!r} has scope {router.scope!r}, "
                f"expected one of {', '.join(_ROUTER_SCOPES)}"
            )
        if not _PREFIX_RE.fullmatch(router.prefix):
            raise ValueError(f"router prefix {router.prefix!r} is not like '/name'")
        if taken := plugin_prefix_conflict(router.prefix, router.scope):
            raise ValueError(
                f"{router.scope} router prefix {router.prefix!r} collides with {taken!r}"
            )


def _validate_pages(pages: list[PageDef], bundle: str | None, scope: str) -> None:
    """Raise if ``pages`` have no bundle to render them, or a bad or reused path."""
    if pages and bundle is None:
        raise ValueError(f"{scope} pages are declared with no {scope} bundle")
    seen: set[str] = set()
    for page in pages:
        if not _PAGE_PATH_RE.fullmatch(page.path):
            raise ValueError(f"{scope} page path {page.path!r} is not like 'a/b'")
        if page.path in seen:
            raise ValueError(f"{scope} page path {page.path!r} is declared twice")
        seen.add(page.path)
        if page.section not in _NAV_SECTIONS:
            raise ValueError(
                f"{scope} page {page.path!r} has section {page.section!r}, "
                f"expected one of {', '.join(_NAV_SECTIONS)}"
            )


def _validate(plugin: Plugin, key: str) -> list[ConfigDef]:
    """Raise if any part of ``plugin`` cannot be registered under ``key``.

    Returns:
        The plugin's normalized config definitions.
    """
    for type_def in plugin.challenge_types:
        challenge_registry.check(type_def.name, key)
    for type_def in plugin.solution_types:
        solution_registry.check(type_def.name, key)
    for job in plugin.jobs:
        scheduler_registry.check(job.type_name, key)
    if plugin.routers:
        _validate_routers(plugin.routers)
    if frontend := plugin.frontend:
        _validate_pages(frontend.user_pages, frontend.entry_file, "user")
        _validate_pages(frontend.admin_pages, frontend.admin_entry_file, "admin")
    return plugin_config_defs(plugin.config, key) if plugin.config else []


def commit_plugin(plugin: Plugin, key: str) -> None:
    """Validate ``plugin`` then register all of it under ``key``.

    Args:
        plugin: The plugin declaration.
        key: The plugin key everything is registered under.
    """
    config_defs = _validate(plugin, key)
    for type_def in plugin.challenge_types:
        challenge_registry.add(type_def, key)
    for type_def in plugin.solution_types:
        solution_registry.add(type_def, key)
    for job in plugin.jobs:
        scheduler_registry.add(job, key)
    for router in plugin.routers:
        route_registry.add(router, key)
    if plugin.config is not None:
        register_config(plugin.config, key, config_defs)
    if plugin.frontend is not None:
        frontend_registry.add(plugin.frontend, key)


def _import_plugin(ep: importlib.metadata.EntryPoint) -> Plugin:
    """Import an entry point and return the :class:`Plugin` it declares."""
    module = importlib.import_module(ep.module)
    plugin = getattr(module, ep.attr or "plugin", None)
    if not isinstance(plugin, Plugin):
        raise TypeError(
            f"entry point {ep.module}:{ep.attr or 'plugin'} is not a nexctf.plugins.Plugin"
        )
    return plugin


def load_builtin_plugins() -> None:
    """Register core's own declarations and the in-tree builtin plugins."""
    for module_path in _CORE_MODULES:
        commit_plugin(importlib.import_module(module_path).plugin, _CORE_KEY)
    for key, module_path in _BUILTINS.items():
        if key in _plugin_metadata:
            continue
        logger.debug("plugin.load name=%s module=%s builtin=true", key, module_path)
        commit_plugin(importlib.import_module(module_path).plugin, key)
        _plugin_metadata[key] = _builtin_metadata(key)


def _disabled_plugin_keys() -> frozenset[str]:
    """Return the plugin keys listed, comma-separated, in ``NEXCTF_DISABLED_PLUGINS``."""
    names = os.environ.get(_DISABLED_ENV, "").split(",")
    return frozenset(plugin_key(n.strip()) for n in names if n.strip())


def _load_installed_plugins(*, include_disabled: bool = False) -> None:
    """Import every installed distribution declaring a ``nexctf.plugins`` entry point.

    Args:
        include_disabled: Load disabled plugins too, as migrations must.
    """
    disabled = frozenset() if include_disabled else _disabled_plugin_keys()
    for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
        if ep.dist is None:
            continue
        key = plugin_key(ep.dist.name)
        if key in _plugin_metadata:
            continue
        if key in disabled:
            logger.info("plugin.disabled name=%s", key)
            _plugin_metadata[key] = _installed_metadata(
                key, ep.dist, is_active=False, is_disabled=True
            )
            continue
        try:
            logger.debug("plugin.load name=%s module=%s", key, ep.module)
            package = ep.module.split(".")[0]
            plugin = _import_plugin(ep)
            # Models and migrations live in the root package, not the entry-point module
            root = importlib.import_module(package)
            owned = derive_owned_tables(package)
            versions = Path(root.__file__ or "").parent / "alembic" / "versions"
            commit_plugin(plugin, key)
            _plugin_metadata[key] = _installed_metadata(key, ep.dist)
            _plugin_tables.update(owned)
            if versions.is_dir():
                _plugin_migrations[key] = (versions, owned)
            elif owned:
                logger.warning(
                    "plugin.migrations.missing key=%s path=%s", key, versions
                )
        except Exception as exc:
            logger.exception("plugin.load_failed name=%s", key)
            _plugin_metadata[key] = _installed_metadata(
                key, ep.dist, is_active=False, load_error=str(exc)
            )


def load_plugin_registries(*, include_disabled: bool = False) -> None:
    """Populate the plugin registries by importing builtin and installed plugins.

    Args:
        include_disabled: Load plugins listed in ``NEXCTF_DISABLED_PLUGINS`` too.
    """
    load_builtin_plugins()
    _load_installed_plugins(include_disabled=include_disabled)


def _patch_crud_classes() -> None:
    """Patch base CRUD classes with plugin-registered load options."""
    from nexctf.crud import ChallengeCrud, SolutionCrud

    challenge_registry.apply(ChallengeCrud)
    solution_registry.apply(SolutionCrud)


def mount_plugin_routes(app: FastAPI) -> None:
    """Mount plugin-registered routers onto the FastAPI app.

    Args:
        app: The FastAPI application to mount the routers on.
    """
    from fastapi import APIRouter

    from nexctf.api.dep import AdminAuthDep, UserAuthDep
    from nexctf.api.scope import reset_table
    from nexctf.core.config import settings

    parents = {
        "admin": APIRouter(
            prefix=f"{settings.API_V1_STR}/admin", dependencies=[AdminAuthDep]
        ),
        "user": APIRouter(prefix=settings.API_V1_STR, dependencies=[UserAuthDep]),
        "anonymous": APIRouter(prefix=settings.API_V1_STR),
    }
    for router in route_registry.get_routers():
        parents[router.scope].include_router(
            router.router, prefix=router.prefix, tags=router.tags
        )
    for parent in parents.values():
        app.include_router(parent)
    reset_table()


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
