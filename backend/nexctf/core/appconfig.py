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
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, cast

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
_CACHE: dict[str, str] = {}  # in-process mirror of the Redis hash


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


def _infer_type(default: str | int | float | bool) -> ConfigType:
    if isinstance(default, bool):
        return ConfigType.BOOL
    if isinstance(default, int):
        return ConfigType.INT
    if isinstance(default, float):
        return ConfigType.FLOAT
    raise ValueError(
        "type= is required when default is a str (cannot infer STRING vs URL vs COLOR vs …)"
    )


def _serialize_default(default: str | int | float | bool) -> str:
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


def get_uncached_keys() -> set[str]:
    """Return keys that are registered but not yet in the in-process cache."""
    return {k for k in _DEFS if k not in _CACHE}


def update_cache(mapping: dict[str, str]) -> None:
    """Merge *mapping* into the in-process config cache."""
    _CACHE.update(mapping)


_ENV_PREFIX = "NEXCTF_"


def _env_key(key: str) -> str:
    return _ENV_PREFIX + key.upper().replace(".", "_")


def _cast(value: str, type_: ConfigType | None) -> str | int | float | bool:
    if type_ == ConfigType.INT:
        return int(value)
    if type_ == ConfigType.FLOAT:
        return float(value)
    if type_ == ConfigType.BOOL:
        return value.lower() in ("1", "true", "yes")
    return value


def get(key: str) -> str | int | float | bool:
    """Resolved value for in-app use: local cache > ENV > code default.

    The local cache (_CACHE) is populated at startup and after writes on
    the same worker. For API responses use ``get_with_overrides`` with a
    fresh Redis snapshot so all workers see the same data.
    """
    def_ = _DEFS[key]
    if key in _CACHE:
        return _cast(_CACHE[key], def_.type)
    env_val = os.environ.get(_env_key(key))
    if env_val is not None:
        return _cast(env_val, def_.type)
    return _cast(cast(str, def_.default), def_.type)


def get_raw(key: str) -> str:
    def_ = _DEFS[key]
    if key in _CACHE:
        return _CACHE[key]
    env_val = os.environ.get(_env_key(key))
    if env_val is not None:
        return env_val
    return cast(str, def_.default)


def get_with_overrides(key: str, overrides: dict[str, str]) -> str | int | float | bool:
    """Resolve value using a caller-supplied overrides dict (e.g. from Redis).

    Use this in API endpoints to get consistent reads across all workers.
    """
    def_ = _DEFS[key]
    if key in overrides:
        return _cast(overrides[key], def_.type)
    env_val = os.environ.get(_env_key(key))
    if env_val is not None:
        return _cast(env_val, def_.type)
    return _cast(cast(str, def_.default), def_.type)


async def fetch_overrides(redis: Redis) -> dict[str, str]:
    """Fetch the current DB overrides from Redis. One round-trip per request."""
    return await cast(Any, redis.hgetall(REDIS_HASH))


async def load_from_db(session: AsyncSession, redis: Redis) -> None:
    """Populate in-process cache on startup.

    Checks Redis first (survives backend restarts). Falls back to DB and
    warms Redis so subsequent restarts skip the DB query.
    """
    cached: dict[str, str] = await cast(Any, redis.hgetall(REDIS_HASH))
    if cached:
        _CACHE.clear()
        for key, value in cached.items():
            if key in _DEFS:
                _CACHE[key] = value
        logger.info("config loaded from Redis (%d entries)", len(_CACHE))
        return

    result = await session.execute(select(ConfigEntry))
    _CACHE.clear()
    mapping: dict[str, str] = {}
    for entry in result.scalars():
        if entry.key in _DEFS:
            _CACHE[entry.key] = entry.value
            mapping[entry.key] = entry.value
        else:
            logger.warning("config.unknown_key key=%s", entry.key)

    if mapping:
        await cast(Any, redis).hset(REDIS_HASH, mapping=mapping)

    logger.info("config loaded from DB (%d entries)", len(_CACHE))


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
    ):
        raise ValueError(f"Invalid boolean: {value!r}")
    elif def_.type == ConfigType.CHOICE and value not in def_.choices:
        raise ValueError(f"Invalid choice: {value!r}, expected one of {def_.choices}")
    elif def_.type == ConfigType.DATETIME and value:
        from datetime import datetime

        try:
            datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"Invalid datetime: {value!r}, expected ISO 8601")
    elif def_.type == ConfigType.COLOR and value:
        import re

        if not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value):
            raise ValueError(f"Invalid color: {value!r}, expected #RRGGBB or #RRGGBBAA")
    elif def_.type == ConfigType.URL and value:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {value!r}")


async def stage(session: AsyncSession, key: str, value: str) -> None:
    """Validate and queue the DB upsert. Does NOT touch the cache.

    Call ``commit_and_cache`` after all keys are staged to atomically
    commit and update both caches.
    """
    _validate(key, value)

    result = await session.execute(select(ConfigEntry).where(ConfigEntry.key == key))
    entry = result.scalar_one_or_none()
    if entry:
        entry.value = value
    else:
        session.add(ConfigEntry(key=key, value=value))


async def commit_and_cache(
    session: AsyncSession, redis: Redis, updates: dict[str, str]
) -> None:
    """Commit all staged changes, then update Redis and in-process cache.

    Caches are only written after a successful commit, so they always
    reflect committed DB state.
    """
    await session.commit()

    pipe = redis.pipeline()
    for key, value in updates.items():
        cast(Any, pipe.hset(REDIS_HASH, key, value))
    await cast(Any, pipe.execute())

    for key, value in updates.items():
        _CACHE[key] = value
