"""Datetime parsing helpers for appconfig values."""

from __future__ import annotations

from datetime import datetime, timezone

import nexctf.core.appconfig as appconfig


def parse_config_dt(key: str) -> datetime | None:
    """Return a timezone-aware datetime from the given appconfig key, or None if unset."""
    raw = str(appconfig.get(key))
    if not raw:
        return None
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
