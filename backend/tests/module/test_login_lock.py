"""Integration tests for nexctf.module.login_lock (real Redis)."""

import uuid
from collections.abc import AsyncGenerator
from typing import NamedTuple

import pytest

from nexctf.module import login_lock
from nexctf.module.login_lock import Counter

ENABLED: dict[str, str] = {}
DISABLED = {"rate_limit.login.enabled": "false"}


class Account(NamedTuple):
    id: uuid.UUID
    username: str


@pytest.fixture
async def account(redis) -> AsyncGenerator[Account]:
    user_id = uuid.uuid4()
    acc = Account(user_id, f"lock-{user_id.hex[:8]}")
    yield acc
    await login_lock.clear(redis, acc.id, acc.username)


async def _fail(redis, counter: Counter, times: int = login_lock.MAX_FAILURES) -> None:
    for _ in range(times):
        await login_lock.record(redis, counter)


def _device(acc: Account, nonce: str) -> Counter:
    return Counter(login_lock.device_key(acc.id, nonce), acc.id)


async def test_locks_the_account_after_the_maximum_failures(redis, account) -> None:
    shared = Counter(login_lock.account_key(account.username))
    await _fail(redis, shared, login_lock.MAX_FAILURES - 1)
    assert not await login_lock.is_locked(redis, ENABLED, *account)
    await _fail(redis, shared, 1)
    assert await login_lock.is_locked(
        redis, ENABLED, account.id, account.username.upper()
    )
    assert not await login_lock.is_locked(redis, DISABLED, *account)


async def test_reports_a_locked_device(redis, account) -> None:
    await _fail(redis, _device(account, "a"))
    assert await login_lock.is_locked(redis, ENABLED, *account)


async def test_clear_drops_only_the_users_counters(redis, account) -> None:
    other = Account(uuid.uuid4(), "unused")
    own = [
        Counter(login_lock.account_key(account.username)),
        _device(account, "a"),
        _device(account, "b"),
    ]
    for counter in [*own, _device(other, "a")]:
        await _fail(redis, counter, 1)

    await login_lock.clear(redis, *account)

    keys = [c.key for c in own] + [login_lock.devices_key(account.id)]
    assert await redis.exists(*keys) == 0
    assert await redis.exists(login_lock.device_key(other.id, "a")) == 1
    await login_lock.clear(redis, *other)
