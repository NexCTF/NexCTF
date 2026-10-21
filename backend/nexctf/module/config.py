"""Config writes shared by the admin API and the ``manager`` CLI."""

from collections.abc import Collection

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core import appconfig
from nexctf.core.eventbus import publish_event
from nexctf.exceptions import ConfigValidationError
from nexctf.module.audit import REDACTED, audit_actor, redact
from nexctf.module.events import emit
from nexctf.module.info import invalidate as invalidate_info
from nexctf.module.scoreboard import invalidate as invalidate_scoreboard
from nexctf.module.stats import invalidate_team
from nexctf.util.datetime import EVENT_TIME_KEYS, event_time_errors


async def save_config(
    session: AsyncSession,
    redis: Redis,
    items: dict[str, str],
    old_overrides: dict[str, str],
) -> dict[str, str]:
    """Validate and store *items*, returning the overrides now in force.

    Raises:
        ConfigValidationError: A key is unknown, a value is invalid or the
            event times end up out of order.
    """
    errors: list[str] = []
    staged: dict[str, str] = {}
    for key, value in items.items():
        if key not in appconfig.all_defs():
            errors.append(f"Unknown key: {key!r}")
            continue
        if (
            value == REDACTED
            and appconfig.get_def(key).type == appconfig.ConfigType.SECRET
        ):
            continue
        try:
            await appconfig.stage(session, key, value)
            staged[key] = value
        except ValueError as e:
            errors.append(f"{key}: {e}")

    overrides = {**old_overrides, **staged}
    _check(errors, overrides, staged.keys())

    await appconfig.commit_and_store(session, redis, staged)
    await _announce(session, redis, old_overrides, overrides, staged.keys())
    return overrides


async def reset_config(
    session: AsyncSession,
    redis: Redis,
    keys: Collection[str],
    old_overrides: dict[str, str],
) -> dict[str, str]:
    """Drop the stored values of *keys* so they fall back to ENV or the default.

    Raises:
        ConfigValidationError: A key is unknown or the event times end up out
            of order.
    """
    errors = [f"Unknown key: {k!r}" for k in keys if k not in appconfig.all_defs()]
    overrides = {k: v for k, v in old_overrides.items() if k not in keys}
    _check(errors, overrides, keys)

    await appconfig.remove_and_store(session, redis, keys)
    await _announce(session, redis, old_overrides, overrides, keys)
    return overrides


def _check(
    errors: list[str], overrides: dict[str, str], changed: Collection[str]
) -> None:
    """Raise the collected *errors*, or event times left out of order."""
    if not errors and EVENT_TIME_KEYS.intersection(changed):
        errors = event_time_errors(overrides)
    if errors:
        raise ConfigValidationError(errors)


async def _announce(
    session: AsyncSession,
    redis: Redis,
    old_overrides: dict[str, str],
    overrides: dict[str, str],
    changed: Collection[str],
) -> None:
    """Refresh the caches a config change affects and record it in the audit log."""
    await invalidate_info(redis)
    if "ctf.freeze_time" in changed:
        await invalidate_scoreboard(redis)
        await invalidate_team(redis)
    await publish_event(redis, ["config:update"], "1")

    if not changed:
        return
    actor_id, ip = audit_actor()
    changes = {
        key: [
            redact(key, appconfig.get_with_overrides(key, old_overrides)),
            redact(key, appconfig.get_with_overrides(key, overrides)),
        ]
        for key in sorted(changed)
    }
    await emit(
        session,
        redis,
        event_type="config.updated",
        actor_id=actor_id,
        ip=ip,
        meta={"changes": changes},
    )
