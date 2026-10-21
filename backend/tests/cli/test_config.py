"""Tests for the config writes shared by ``manager config`` and the admin API."""

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core import appconfig
from nexctf.exceptions import ConfigValidationError
from nexctf.model import Event
from nexctf.module.config import reset_config, save_config

KEY = "rate_limit.login.max_requests"


async def test_reset_falls_back_to_the_default(
    db_session: AsyncSession, mock_redis
) -> None:
    """A reset key loses its stored value and is dropped from Redis."""
    stored = await save_config(db_session, mock_redis, {KEY: "42"}, {})
    assert stored[KEY] == "42"

    overrides = await reset_config(db_session, mock_redis, [KEY], stored)

    assert KEY not in overrides
    assert KEY not in await appconfig.stored_overrides(db_session)
    mock_redis.hdel.assert_awaited_once_with(appconfig.REDIS_HASH, KEY)
    events = (await db_session.scalars(select(Event).order_by(Event.created_at))).all()
    assert [e.meta["changes"][KEY] for e in events] == [[10, 42], [42, 10]]


@pytest.mark.parametrize(
    ("write", "items", "error"),
    [
        (save_config, {KEY: "many"}, KEY),
        (save_config, {"nope.key": "1"}, "Unknown key"),
        (reset_config, ["nope.key"], "Unknown key"),
        (
            save_config,
            {
                "ctf.start_time": "2030-01-02T00:00:00Z",
                "ctf.end_time": "2030-01-01T00:00:00Z",
            },
            "",
        ),
    ],
    ids=["bad-value", "unknown-save", "unknown-reset", "event-order"],
)
async def test_invalid_writes_store_nothing(
    db_session: AsyncSession,
    mock_redis,
    write: Callable[..., Awaitable[dict[str, str]]],
    items: dict[str, str] | list[str],
    error: str,
) -> None:
    with pytest.raises(ConfigValidationError) as raised:
        await write(db_session, mock_redis, items, {})

    assert error in str(raised.value.api_error.desc)
    await db_session.rollback()
    assert await appconfig.stored_overrides(db_session) == {}
