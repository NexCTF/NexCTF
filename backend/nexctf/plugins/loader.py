"""Plugin discovery, loading, and FastAPI wiring.

Builtin plugins
    Discovered by scanning every ``plugins/builtin/*/pyproject.toml`` for
    ``[project.entry-points."nexctf.plugins"]`` entries and importing the
    declared modules.

Store (user-provided) plugins
    Placed manually in ``plugins_store/``. Their dependencies are installed and
    migrations run by ``scripts/start.sh`` at container start; this loader then
    builds the frontend and imports the entry point.

Call ``init_plugins(app, session)`` from the FastAPI lifespan after
``nexctf.core.appconfig.load_from_db``.
"""

from __future__ import annotations

import importlib
import logging
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_loaded: dict[str, ModuleType] = {}
_BUILTIN_DIR = Path(__file__).parent / "builtin"
_STORE_DIR = Path(__file__).parent.parent.parent / "plugins_store"
_plugin_tables: set[str] = set()
_plugin_metadata: dict[str, "PluginMeta"] = {}


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


def read_pyproject(path: Path) -> dict:
    """Load and parse a plugin's ``pyproject.toml``.

    Args:
        path: Path to the ``pyproject.toml`` file.

    Returns:
        The parsed TOML document.
    """
    with path.open("rb") as f:
        return tomllib.load(f)


def get_entry_points(data: dict) -> dict[str, str]:
    """Extract the ``nexctf.plugins`` entry points from pyproject data.

    Args:
        data: A parsed ``pyproject.toml`` document.

    Returns:
        A mapping of entry-point name to dotted module path.
    """
    return data.get("project", {}).get("entry-points", {}).get("nexctf.plugins", {})


def parse_plugin_metadata(
    key: str,
    data: dict,
    *,
    is_builtin: bool,
    is_active: bool = True,
    load_error: str | None = None,
) -> PluginMeta:
    """Build a :class:`PluginMeta` from a parsed ``pyproject.toml`` document.

    Args:
        key: Entry-point name used as the plugin's key.
        data: A parsed ``pyproject.toml`` document.
        is_builtin: Whether the plugin ships in-tree.
        is_active: Whether the plugin loaded successfully.
        load_error: Error message captured when loading failed, if any.

    Returns:
        The assembled metadata.
    """
    project = data.get("project", {})
    nexctf = data.get("tool", {}).get("nexctf", {})
    urls = project.get("urls", {})
    authors_raw = project.get("authors", [])
    authors = [
        a.get("name", "") for a in authors_raw if isinstance(a, dict) and a.get("name")
    ]
    name = project.get("name", key)
    display_name = nexctf.get("display_name", name)
    return PluginMeta(
        key=key,
        name=name,
        display_name=display_name,
        version=project.get("version"),
        description=project.get("description"),
        authors=authors,
        repo_url=urls.get("Repository") or urls.get("repository"),
        homepage_url=urls.get("Homepage") or urls.get("homepage"),
        is_builtin=is_builtin,
        is_active=is_active,
        load_error=load_error,
    )


def register_plugin_tables(*table_names: str) -> None:
    """Register table names owned by a plugin.

    Args:
        *table_names: Table names the main Alembic autogenerate must ignore.
    """
    _plugin_tables.update(table_names)


def derive_owned_tables(model_modules: Iterable[str]) -> frozenset[str]:
    """Derive the table names a plugin owns from its model modules.

    Imports each module so its mapped classes register with SQLAlchemy, then
    collects the table name of every mapper defined in those modules. This makes
    a model's ``__tablename__`` the single source of truth, so plugin authors
    never restate table names in ``pyproject.toml``.

    Args:
        model_modules: Dotted paths to the plugin's model modules (the
            ``[tool.nexctf.migrations].models`` pyproject entries).

    Returns:
        The set of table names declared by models in those modules.
    """
    from sqlalchemy import Table

    from nexctf.model import Base

    modules = set(model_modules)
    for module in modules:
        importlib.import_module(module)
    return frozenset(
        mapper.local_table.name
        for mapper in Base.registry.mappers
        if mapper.class_.__module__ in modules and isinstance(mapper.local_table, Table)
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
        A mapping of entry-point name to :class:`PluginMeta`.
    """
    return _plugin_metadata


def _load_plugins_from_dir(
    directory: Path,
    *,
    is_builtin: bool,
    build_frontend: bool = False,
) -> None:
    """Scan ``directory/*/pyproject.toml``, build frontends, and import entry points.

    Builtin (in-tree) load failures propagate — they are code bugs and must be
    fatal. A store plugin that fails any step is instead recorded in the metadata
    with ``is_active=False`` and a ``load_error`` so the admin UI can surface it.

    Args:
        directory: Directory whose immediate subdirectories hold plugins.
        is_builtin: Whether the directory holds in-tree builtin plugins.
        build_frontend: Whether to build each plugin's frontend bundle.
    """
    if not directory.exists():
        return
    for pyproject_path in sorted(directory.glob("*/pyproject.toml")):
        plugin_dir = pyproject_path.parent
        data = read_pyproject(pyproject_path)
        entry_points = get_entry_points(data)
        try:
            if build_frontend:
                from nexctf.plugins.frontend import build_plugin_frontend

                plugin_name = data.get("project", {}).get("name", plugin_dir.name)
                build_plugin_frontend(plugin_dir, plugin_name)
            for ep_name, module_path in entry_points.items():
                if ep_name not in _loaded:
                    logger.debug("plugin.load name=%s module=%s", ep_name, module_path)
                    _loaded[ep_name] = importlib.import_module(module_path)
                    _plugin_metadata[ep_name] = parse_plugin_metadata(
                        ep_name, data, is_builtin=is_builtin
                    )
            migrations = data.get("tool", {}).get("nexctf", {}).get("migrations", {})
            register_plugin_tables(*derive_owned_tables(migrations.get("models", [])))
        except Exception as exc:
            if is_builtin:
                raise
            logger.exception("plugin.load_failed dir=%s", plugin_dir)
            for key in list(entry_points) or [plugin_dir.name]:
                if key not in _plugin_metadata:
                    _plugin_metadata[key] = parse_plugin_metadata(
                        key,
                        data,
                        is_builtin=is_builtin,
                        is_active=False,
                        load_error=str(exc),
                    )


def load_builtin_plugins() -> None:
    """Scan ``plugins/builtin/`` and import every declared entry point."""
    _load_plugins_from_dir(_BUILTIN_DIR, is_builtin=True)


def _load_store_plugins() -> None:
    """Build frontends and import plugins placed in ``plugins_store/``.

    Dependency installation and migrations are handled by ``scripts/start.sh``.
    """
    if not _STORE_DIR.exists():
        return
    if str(_STORE_DIR) not in sys.path:
        sys.path.insert(0, str(_STORE_DIR))
    _load_plugins_from_dir(_STORE_DIR, is_builtin=False, build_frontend=True)


def _setup_registries() -> None:
    """Configure registry defaults that require model imports.

    Runs before plugins load so their ``register()`` calls inherit the defaults.
    """
    from nexctf.model.challenge import Challenge
    from nexctf.plugins.registry import challenge_registry

    challenge_registry.set_base_m2m_fields({"tags_ids": Challenge.tags})


def load_plugin_registries() -> None:
    """Populate the plugin registries by importing builtin and store plugins.

    Shared by the API lifespan (via :func:`init_plugins`) and the worker, which
    calls it as its sole initialization step. It performs no API-specific work
    (route mounting, CRUD patching) so it is safe for background job execution.
    """
    _setup_registries()
    load_builtin_plugins()
    _load_store_plugins()


def _patch_crud_classes() -> None:
    """Patch base CRUD classes with plugin-registered load options."""
    from nexctf.crud import ChallengeCrud, SolutionCrud
    from nexctf.plugins.registry import challenge_registry, solution_registry

    challenge_registry.apply(ChallengeCrud)
    solution_registry.apply(SolutionCrud)


async def _reconcile_configs(session: "AsyncSession") -> None:
    """Warm the Redis/DB cache for plugin config keys registered late.

    Args:
        session: An open async database session.
    """
    from nexctf.core.cache import get_client as get_redis_client
    from nexctf.plugins.config import reconcile_plugin_configs

    await reconcile_plugin_configs(session, get_redis_client())


def mount_plugin_routes(app: "FastAPI") -> None:
    """Mount plugin-registered routers onto the FastAPI app.

    Call after all plugins are loaded so every registered route is included.

    Args:
        app: The FastAPI application to mount the routers on.
    """
    from fastapi import APIRouter, Security

    from nexctf.api.security import auth
    from nexctf.core.config import settings
    from nexctf.model import UserRole
    from nexctf.plugins.routes import route_registry

    _admin = APIRouter(
        prefix=f"{settings.API_V1_STR}/admin",
        dependencies=[Security(auth.require(role=UserRole.admin))],
    )
    _public = APIRouter(prefix=settings.API_V1_STR)

    for r, prefix, tags in route_registry.get_routers(scope="admin"):
        _admin.include_router(r, prefix=prefix, tags=tags)
    for r, prefix, tags in route_registry.get_routers(scope="public"):
        _public.include_router(r, prefix=prefix, tags=tags)

    app.include_router(_admin)
    app.include_router(_public)


async def init_plugins(app: "FastAPI", session: "AsyncSession") -> None:
    """Load all plugins, patch CRUD classes, reconcile configs, and mount routes.

    Calls :func:`load_plugin_registries` then performs the API-specific steps
    (CRUD patching, config reconciliation, route mounting). Idempotent — safe to
    call multiple times (e.g. in tests).

    Call from the FastAPI lifespan after ``nexctf.core.appconfig.load_from_db``.

    Args:
        app: The FastAPI application to wire plugin routes into.
        session: An open async database session.
    """
    load_plugin_registries()
    _patch_crud_classes()
    await _reconcile_configs(session)
    mount_plugin_routes(app)
