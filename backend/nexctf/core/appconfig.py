"""Application configuration system.

Resolution order for each key: code default → ENV variable → DB override.

Config definitions are declared in ``nexctf/settings.py``.  The
``label`` and ``description`` fields store **i18n keys** (not raw text),
so the frontend can resolve them with their own translation files.

Plugin-specific config (register_plugin_configs, get_plugin_config)
lives in ``nexctf.plugins.config``.
"""

from __future__ import annotations

import enum
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlparse

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model.config import ConfigEntry

logger = logging.getLogger(__name__)

REDIS_HASH = "nexctf:config"


class ConfigType(str, enum.Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    CHOICE = "choice"
    DATETIME = "datetime"
    COLOR = "color"
    URL = "url"
    TEXT = "text"  # multiline string


@dataclass(frozen=True)
class ConfigDef:
    key: str
    label: str  # i18n key
    default: str | int | float | bool = ""
    description: str = ""  # i18n key
    type: ConfigType | None = None  # inferred from default for bool/int/float
    choices: list[str] = field(default_factory=list)
    category: str = "general"


_DEFS: dict[str, ConfigDef] = {}


@dataclass(frozen=True)
class CategoryMeta:
    label: str  # i18n key or plain display name
    section: str  # sidebar section slug (e.g. "settings", "plugins")
    icon: str | None  # Lucide icon name in kebab-case, e.g. "trophy"
    is_plugin: bool


_CATEGORIES: dict[str, CategoryMeta] = {}

_DEFAULT_CATEGORY = CategoryMeta(
    label="general", section="settings", icon=None, is_plugin=False
)


def _infer_type(default: str | float | bool) -> ConfigType:
    if isinstance(default, bool):
        return ConfigType.BOOL
    if isinstance(default, int):
        return ConfigType.INT
    if isinstance(default, float):
        return ConfigType.FLOAT
    raise ValueError(
        "type= is required when default is a str (cannot infer STRING vs URL vs COLOR vs …)"
    )


def _serialize_default(default: str | float | bool) -> str:
    if isinstance(default, bool):
        return "true" if default else "false"
    return str(default)


def define(def_: ConfigDef) -> None:
    type_ = def_.type if def_.type is not None else _infer_type(def_.default)
    normalized = replace(def_, type=type_, default=_serialize_default(def_.default))
    _DEFS[normalized.key] = normalized
    _CATEGORIES.setdefault(
        normalized.category,
        CategoryMeta(
            label=normalized.category, section="settings", icon=None, is_plugin=False
        ),
    )


def register_category(
    slug: str,
    label: str,
    *,
    section: str = "settings",
    icon: str | None = None,
    is_plugin: bool = False,
) -> None:
    """Register (or overwrite) category metadata.

    Args:
        slug:      Unique category identifier, used as ``ConfigDef.category``.
        label:     Display name shown in the sidebar. Use an i18n key for
                   built-in categories (e.g. ``"config.category.competition"``),
                   or a plain string for plugin categories.
        section:   Sidebar section slug. Built-in sections are ``"settings"``
                   and ``"plugins"``.  Pass any custom slug to create a new
                   section; its display name resolves via
                   ``t("config.section.<slug>", { defaultValue: slug })``.
        icon:      Lucide icon name in kebab-case (e.g. ``"trophy"``,
                   ``"bar-chart"``, ``"puzzle"``). Optional.
        is_plugin: Set by :func:`register_plugin_configs`; marks the category
                   as coming from a plugin.
    """
    _CATEGORIES[slug] = CategoryMeta(
        label=label, section=section, icon=icon, is_plugin=is_plugin
    )


def get_category_meta(slug: str) -> CategoryMeta:
    return _CATEGORIES.get(slug, _DEFAULT_CATEGORY)


class ConfigRegistry:
    """Decorator-based registry for grouping config definitions by category.

    Example (in ``settings.py``)::

        config = ConfigRegistry()

        @config.category("competition", "config.category.competition", icon="trophy")
        def _competition():
            return [
                ConfigDef(key="ctf.name", label="config.ctf.name.label", default="NexCTF",
                          type=ConfigType.STRING),
                ConfigDef(key="ctf.team_size", label="config.ctf.team_size.label", default=4),
                ConfigDef(key="ctf.allow_registration", label="...", default=True),
            ]
    """

    def category(
        self,
        slug: str,
        label: str,
        *,
        section: str = "settings",
        icon: str | None = None,
    ) -> Callable:
        def decorator(
            fn: Callable[[], list[ConfigDef]],
        ) -> Callable[[], list[ConfigDef]]:
            register_category(slug, label, section=section, icon=icon)
            for def_ in fn():
                define(replace(def_, category=slug))
            return fn

        return decorator


def get_def(key: str) -> ConfigDef:
    return _DEFS[key]


def all_defs() -> dict[str, ConfigDef]:
    return _DEFS


_ENV_PREFIX = "NEXCTF_"


def _env_key(key: str) -> str:
    return _ENV_PREFIX + key.upper().replace(".", "_")


def _cast(value: str, type_: ConfigType | None) -> str | int | float | bool:
    if type_ == ConfigType.INT:
        return int(value)
    if type_ == ConfigType.FLOAT:
        return float(value)
    if type_ == ConfigType.BOOL:
        return value.lower() in ("1", "true", "yes", "on")
    return value


_warned: set[str] = set()


def get_with_overrides(
    key: str, overrides: dict[str, str], *, sanitize: bool = True
) -> str | int | float | bool:
    """Resolve a value: Redis snapshot > ENV > code default."""
    def_ = _DEFS[key]
    raw = overrides.get(key)
    if raw is None:
        raw = os.environ.get(_env_key(key))
    if raw is not None and sanitize:
        try:
            _validate(key, raw)
        except ValueError as exc:
            if key not in _warned:
                _warned.add(key)
                logger.warning("invalid config %s (%s), using default", key, exc)
            raw = None
    return _cast(cast(str, def_.default) if raw is None else raw, def_.type)


async def fetch_overrides(redis: Redis) -> dict[str, str]:
    """Fetch the current DB overrides from Redis. One round-trip per request."""
    return await cast(Any, redis.hgetall(REDIS_HASH))


async def sync_to_redis(session: AsyncSession, redis: Redis) -> None:
    """Mirror every stored config value from the database into Redis.

    Idempotent — call at startup and again once plugins register their keys.
    """
    result = await session.execute(select(ConfigEntry.key, ConfigEntry.value))
    stored = {key: value for key, value in result.all() if key in _DEFS}
    if stored:
        await cast(Any, redis).hset(REDIS_HASH, mapping=stored)
    logger.info("config synced to Redis (%d keys)", len(stored))


def _validate(key: str, value: str) -> None:
    """Raise ValueError if value is invalid for the key's type."""
    def_ = _DEFS[key]

    if def_.type == ConfigType.INT:
        int(value)
    elif def_.type == ConfigType.FLOAT:
        float(value)
    elif def_.type == ConfigType.BOOL and value.lower() not in (
        "1",
        "0",
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
    ):
        raise ValueError(f"Invalid boolean: {value!r}")
    elif def_.type == ConfigType.CHOICE and value not in def_.choices:
        raise ValueError(f"Invalid choice: {value!r}, expected one of {def_.choices}")
    elif def_.type == ConfigType.DATETIME and value:
        try:
            datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"Invalid datetime: {value!r}, expected ISO 8601")
    elif def_.type == ConfigType.COLOR and value:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value):
            raise ValueError(f"Invalid color: {value!r}, expected #RRGGBB or #RRGGBBAA")
    elif def_.type == ConfigType.URL and value:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {value!r}")


async def stage(session: AsyncSession, key: str, value: str) -> None:
    """Validate and queue the DB upsert. Does NOT touch the cache.

    Call ``commit_and_store`` after all keys are staged to atomically
    commit and update both caches.
    """
    _validate(key, value)

    result = await session.execute(select(ConfigEntry).where(ConfigEntry.key == key))
    entry = result.scalar_one_or_none()
    if entry:
        entry.value = value
    else:
        session.add(ConfigEntry(key=key, value=value))


async def commit_and_store(
    session: AsyncSession, redis: Redis, updates: dict[str, str]
) -> None:
    """Commit all staged changes, then publish them to Redis."""
    await session.commit()

    pipe = redis.pipeline()
    for key, value in updates.items():
        cast(Any, pipe.hset(REDIS_HASH, key, value))
    await cast(Any, pipe.execute())
