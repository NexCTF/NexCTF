"""Plugin system package.

Loading and FastAPI wiring live in :mod:`nexctf.plugins.loader`; the registries
and config helpers plugin authors call live in the sibling modules. This module
re-exports the public surface so plugins can ``from nexctf.plugins import ...``
and never reach into private internals.
"""

from __future__ import annotations

from nexctf.core.appconfig import ConfigDef, ConfigType
from nexctf.enums import InputType
from nexctf.plugins.config import get_plugin_config, register_plugin_configs
from nexctf.plugins.frontend import frontend_registry
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
from nexctf.plugins.routes import route_registry

__all__ = [  # noqa: RUF022
    # registries — what plugins register themselves with
    "challenge_registry",
    "solution_registry",
    "scheduler_registry",
    "frontend_registry",
    "route_registry",
    # config helpers
    "register_plugin_configs",
    "get_plugin_config",
    "ConfigDef",
    "ConfigType",
    "InputType",
    # loading — called by the app, not by plugins
    "init_plugins",
    "load_plugin_registries",
    "load_builtin_plugins",
    "mount_plugin_routes",
    "get_plugin_metadata",
    "get_plugin_tables",
    "PluginMeta",
]
