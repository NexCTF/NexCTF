"""Sign-in lockout: wrong-guess counters per account and per known device."""

from typing import Any, NamedTuple, cast
from uuid import UUID

from redis.asyncio import Redis

from nexctf.core import appconfig
from nexctf.core.rate_limit import (
    check_failure_limit,
    failure_limit_reached,
    record_failure,
)

MAX_FAILURES = 20
WINDOW_SECONDS = 900


class Counter(NamedTuple):
    """A failure counter; ``device_owner`` is set for a known browser's counter."""

    key: str
    device_owner: UUID | None = None


def account_key(username: str) -> str:
    """Key shared by every client without a device cookie for *username*."""
    return f"rl:login_fail:{username.lower()}"


def device_key(user_id: UUID, nonce: str) -> str:
    """Key of one known browser of *user_id*."""
    return f"rl:login_fail_device:{user_id}:{nonce}"


def devices_key(user_id: UUID) -> str:
    """Set of the device keys *user_id* collected failures on."""
    return f"rl:login_devices:{user_id}"


def _enabled(overrides: dict[str, str]) -> bool:
    return bool(appconfig.get_with_overrides("rate_limit.login.enabled", overrides))


async def check(redis: Redis, overrides: dict[str, str], counter: Counter) -> None:
    """Refuse a sign-in once *counter* collected too many wrong guesses."""
    if _enabled(overrides):
        await check_failure_limit(
            redis,
            counter.key,
            window_seconds=WINDOW_SECONDS,
            max_failures=MAX_FAILURES,
            name="login_account",
        )


async def record(redis: Redis, counter: Counter) -> None:
    """Count one wrong guess on *counter*, tracking device keys per user."""
    await record_failure(redis, counter.key, window_seconds=WINDOW_SECONDS)
    if counter.device_owner is not None:
        devices = devices_key(counter.device_owner)
        await redis.sadd(devices, counter.key)
        await redis.expire(devices, WINDOW_SECONDS + 1)


async def _keys(redis: Redis, user_id: UUID, username: str) -> list[str]:
    """The account key and every tracked device key of the user."""
    devices: set[str] = await cast(Any, redis.smembers(devices_key(user_id)))
    return [account_key(username), *devices]


async def is_locked(
    redis: Redis, overrides: dict[str, str], user_id: UUID, username: str
) -> bool:
    """Whether the account's shared counter, or one of its browsers, is locked."""
    if not _enabled(overrides):
        return False
    for key in await _keys(redis, user_id, username):
        if await failure_limit_reached(
            redis, key, window_seconds=WINDOW_SECONDS, max_failures=MAX_FAILURES
        ):
            return True
    return False


async def clear(redis: Redis, user_id: UUID, username: str) -> None:
    """Drop the account counter and every device counter of the user."""
    keys = await _keys(redis, user_id, username)
    await redis.delete(*keys, devices_key(user_id))
