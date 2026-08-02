"""Plugin configuration registration and resolution.

Plugins call:
  - register_plugin_configs() — declare config keys with a plugin prefix
  - get_plugin_config()       — resolve a config value with auto-prefix

Category infrastructure (CategoryMeta, register_category, get_category_meta)
lives in core/appconfig.py because both core and plugin configs share it.
"""

from __future__ import annotations

import sys
from dataclasses import replace

from nexctf.core.appconfig import (
    ConfigDef,
    define,
    get_with_overrides,
    register_category,
)


def _caller_slug(depth: int = 2) -> str:
    """Derive the plugin slug from the caller's package name.

    Walks up the call stack by ``depth`` frames and extracts the last
    component of ``__package__`` (e.g. ``"nexctf_container"`` → ``"container"``).

    Args:
        depth: Number of stack frames to walk up to reach the plugin caller.

    Returns:
        The derived slug, or an empty string when no package is found.
    """
    pkg = sys._getframe(depth).f_globals.get("__package__", "")
    return pkg.rsplit(".", 1)[-1] if pkg else ""


def register_plugin_configs(
    display_name: str,
    *defs: ConfigDef,
    icon: str | None = None,
    section: str = "plugins",
    plugin_slug: str | None = None,
) -> None:
    """Register config definitions for a plugin.

    The plugin slug is derived automatically from the caller's package name
    (last component of ``__package__``).  Keys are prefixed with
    ``{slug}.`` automatically — pass bare names like ``"docker_host"`` and
    they become ``"container.docker_host"``.

    Args:
        display_name: Human-readable label shown in the settings sidebar.
        *defs:        :class:`ConfigDef` instances — use bare key names.
        icon:         Optional Lucide icon name, e.g. ``"box"``.
        section:      Sidebar section. Defaults to ``"plugins"``.
        plugin_slug:  Explicit slug override. Inferred from caller package when omitted.

    Example (inside ``nexctf_orchestrator/__init__.py``)::

        register_plugin_configs(
            "Orchestrator",
            ConfigDef(key="instance_url", label="Instance URL",
                      default="http://localhost:9000", type=ConfigType.URL),
            ConfigDef(key="enabled", label="Enable plugin", default=True),
            icon="box",
        )
    """
    slug = plugin_slug or _caller_slug(depth=2)
    register_category(slug, display_name, section=section, icon=icon, is_plugin=True)
    prefix = f"{slug}."
    for def_ in defs:
        key = def_.key if def_.key.startswith(prefix) else f"{prefix}{def_.key}"
        define(replace(def_, key=key, category=slug))


def get_plugin_config(
    key: str,
    overrides: dict[str, str],
    *,
    plugin_slug: str | None = None,
) -> str | int | float | bool:
    """Resolve a plugin config value using the caller's package as the slug.

    Call from anywhere inside the plugin package and the prefix is resolved
    automatically.

    Args:
        key:         Bare config key, e.g. ``"instance_url"``.
        overrides:   Config snapshot from ``appconfig.fetch_overrides``.
        plugin_slug: Explicit slug override. Inferred from caller package when omitted.

    Example (inside ``orchestrator/module/orchestrator.py``)::

        host = get_plugin_config("instance_url", overrides)
    """
    slug = plugin_slug or _caller_slug(depth=2)
    prefix = f"{slug}."
    full_key = key if key.startswith(prefix) else f"{prefix}{key}"
    return get_with_overrides(full_key, overrides)
