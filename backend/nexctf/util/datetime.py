"""Datetime parsing helpers for appconfig values."""

from __future__ import annotations

from datetime import UTC, datetime

from nexctf.core import appconfig


def parse_config_dt(key: str, overrides: dict[str, str]) -> datetime | None:
    """Return a timezone-aware datetime from the given appconfig key, or None if unset."""
    raw = str(appconfig.get_with_overrides(key, overrides))
    if not raw:
        return None
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def is_config_dt_past(key: str, overrides: dict[str, str]) -> bool:
    """Return True if the given appconfig datetime key is set and in the past."""
    dt = parse_config_dt(key, overrides)
    return dt is not None and datetime.now(UTC) > dt
