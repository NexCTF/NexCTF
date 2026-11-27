"""Tests for the helpers shared by the ``manager`` command groups."""

import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import typer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from typer.testing import CliRunner

from nexctf.cli.common import CliError, command
from nexctf.cli.ratelimit import clear_limits, live_counts
from nexctf.core.rate_limit import rate_key
from nexctf.module.events import (
    AuditContext,
    current_audit_context,
    emit,
    set_audit_context,
)


def test_cli_error_is_a_one_line_failure() -> None:
    """A refused command prints ``Error: ...`` and exits 1, with no traceback."""
    app = typer.Typer()

    @app.command()
    @command
    async def refuse() -> None:
        raise CliError("nope")

    result = CliRunner().invoke(app, [])

    assert result.exit_code == 1
    assert "Error: nope" in result.output
    assert "Traceback" not in result.output
    assert current_audit_context() is None


async def test_clear_limits_narrows_to_an_address() -> None:
    """Clearing with an IP only matches that address's window."""
    redis = MagicMock()
    matched: list[str] = []

    async def scan_iter(match: str) -> AsyncIterator[str]:
        matched.append(match)
        yield "rl:login:203.0.113.5"

    redis.scan_iter = scan_iter
    redis.delete = AsyncMock()

    assert await clear_limits(redis, "login", "203.0.113.5") == 1
    assert matched == ["rl:login:203.0.113.5"]
    redis.delete.assert_awaited_once_with("rl:login:203.0.113.5")


async def test_live_counts_skip_requests_outside_the_window(redis: Redis) -> None:
    """Only requests inside the action's window are counted."""
    action = f"test{uuid4().hex}"
    now = time.time()
    await redis.zadd(rate_key(action, "203.0.113.6"), {"old": now - 120, "new": now})
    await redis.zadd(rate_key(action, "203.0.113.7"), {"old": now - 120})
    try:
        assert await live_counts(redis, action, None) == {"203.0.113.6": 1}
    finally:
        await redis.delete(
            rate_key(action, "203.0.113.6"), rate_key(action, "203.0.113.7")
        )


async def test_audit_context_source_tags_events(db_session: AsyncSession) -> None:
    """Events emitted under a CLI audit context carry ``source=cli``."""
    set_audit_context(AuditContext(actor_id=None, ip=None, source="cli"))

    event = await emit(db_session, event_type="t.cli", meta={"k": "v"})

    assert event.meta == {"k": "v", "source": "cli"}
