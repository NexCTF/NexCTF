"""Plugin configuration registration and resolution.

A plugin's config keys live under its plugin key: ``token`` declared by the
``nexctf_plugin_orchestrator`` distribution is stored as
``nexctf_plugin_orchestrator.token``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import replace

from nexctf.core.appconfig import (
    ConfigDef,
    ConfigType,
    define,
    get_with_overrides,
    normalize_def,
    register_category,
)
from nexctf.plugins.declare import ConfigCategory

logger = logging.getLogger(__name__)

_SECRET_LIKE = re.compile(r"token|secret|password|api_key", re.IGNORECASE)


def plugin_config_defs(category: ConfigCategory, key: str) -> list[ConfigDef]:
    """Return a plugin's config definitions, prefixed and normalized.

    Raises:
        ValueError: If a definition is invalid.
    """
    return [
        normalize_def(replace(def_, key=f"{key}.{def_.key}", category=key))
        for def_ in category.defs
    ]


def register_config(category: ConfigCategory, key: str, defs: list[ConfigDef]) -> None:
    """Define a plugin's config keys and bind its category to the plugin key.

    Args:
        category: The plugin's config declaration.
        key: The plugin key, used as category slug and key prefix.
        defs: The category's definitions from :func:`plugin_config_defs`.
    """
    register_category(
        key,
        category.display_name,
        section=category.section,
        icon=category.icon,
        is_plugin=True,
    )
    for def_ in defs:
        if _SECRET_LIKE.search(def_.key) and def_.type is not ConfigType.SECRET:
            logger.warning(
                "plugin.config.plain_secret key=%s: declare it ConfigType.SECRET "
                "so it is masked on read and left out of bundle exports",
                def_.key,
            )
        define(def_)
    category.key = key


def get_plugin_config(
    key: str, overrides: dict[str, str], *, plugin_key: str
) -> str | int | float | bool:
    """Resolve a config value of the plugin registered under ``plugin_key``.

    Plugins holding their :class:`ConfigCategory` can call its ``get`` instead.

    Args:
        key: Bare config key, e.g. ``"instance_url"``.
        overrides: Config snapshot from ``appconfig.fetch_overrides``.
        plugin_key: The plugin the key belongs to.
    """
    return get_with_overrides(f"{plugin_key}.{key}", overrides)
