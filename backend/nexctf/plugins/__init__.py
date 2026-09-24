"""Plugin system package.

A plugin's entry point resolves to a :class:`Plugin` declaring everything it
contributes; the loader in :mod:`nexctf.plugins.loader` validates it and
registers all of it at once. This module re-exports the public surface so
plugins can ``from nexctf.plugins import ...`` and never reach into internals.
"""

from __future__ import annotations

from nexctf.core.appconfig import ConfigDef, ConfigType
from nexctf.enums import InputType
from nexctf.plugins.config import get_plugin_config
from nexctf.plugins.declare import (
    ConfigCategory,
    FrontendDef,
    JobDef,
    PageDef,
    Plugin,
    RouterDef,
    TypeDef,
)
from nexctf.plugins.loader import (
    PluginMeta,
    get_plugin_metadata,
    get_plugin_tables,
    init_plugins,
    load_builtin_plugins,
    load_plugin_registries,
    mount_plugin_routes,
)
from nexctf.plugins.registry import (
    challenge_registry,
    scheduler_registry,
    solution_registry,
)

__all__ = [  # noqa: RUF022
    # declaration: what a plugin's entry point exposes
    "Plugin",
    "TypeDef",
    "JobDef",
    "RouterDef",
    "FrontendDef",
    "PageDef",
    "ConfigCategory",
    "ConfigDef",
    "ConfigType",
    "InputType",
    # runtime helpers
    "get_plugin_config",
    "challenge_registry",
    "solution_registry",
    "scheduler_registry",
    # loading: called by the app, not by plugins
    "init_plugins",
    "load_plugin_registries",
    "load_builtin_plugins",
    "mount_plugin_routes",
    "get_plugin_metadata",
    "get_plugin_tables",
    "PluginMeta",
]
