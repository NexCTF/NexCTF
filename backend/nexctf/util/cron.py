"""Cron expression parsing for scheduler jobs.

Expressions are evaluated in the event timezone (``ctf.timezone``) so that
"every day at midnight" survives daylight-saving shifts, and the fire times are
returned in UTC, which is what the scheduler stores and compares against.
"""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cronsim import CronSim, CronSimError


def resolve_zone(name: str | None) -> tzinfo:
    """Return the named zone, falling back to UTC when it is unset or unknown."""
    if not name:
        return UTC
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        return UTC


def next_fires(
    expr: str, after: datetime, count: int = 1, tz: str | None = None
) -> list[datetime]:
    """Return the *count* first fire times strictly after *after*, in UTC.

    Raises:
        CronSimError: The expression is malformed, or never fires.
    """
    iterator = CronSim(expr, after.astimezone(resolve_zone(tz)))
    try:
        return [next(iterator).astimezone(UTC) for _ in range(count)]
    except StopIteration:
        raise CronSimError(f"expression has no fire time: {expr}") from None


def next_fire(expr: str, after: datetime, tz: str | None = None) -> datetime:
    """Return the first fire time strictly after *after*, in UTC."""
    return next_fires(expr, after, tz=tz)[0]


def validate_cron(expr: str) -> str:
    """Pydantic validator rejecting malformed cron expressions."""
    try:
        next_fire(expr, datetime.now(UTC))
    except CronSimError as exc:
        raise ValueError(f"invalid cron expression: {exc}") from exc
    return expr
