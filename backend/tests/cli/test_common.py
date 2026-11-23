"""Tests for the helpers shared by the ``manager`` command groups."""

from unittest.mock import AsyncMock, MagicMock

import typer
from sqlalchemy.ext.asyncio import AsyncSession
from typer.testing import CliRunner

from nexctf.cli.common import CliError, command
from nexctf.cli.ratelimit import clear_limits
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

    async def scan_iter(match: str):
        matched.append(match)
        yield "rl:login:203.0.113.5"

    redis.scan_iter = scan_iter
    redis.delete = AsyncMock()

    assert await clear_limits(redis, "login", "203.0.113.5") == 1
    assert matched == ["rl:login:203.0.113.5"]
    redis.delete.assert_awaited_once_with("rl:login:203.0.113.5")


async def test_audit_context_source_tags_events(db_session: AsyncSession) -> None:
    """Events emitted under a CLI audit context carry ``source=cli``."""
    set_audit_context(AuditContext(actor_id=None, ip=None, source="cli"))

    event = await emit(db_session, event_type="t.cli", meta={"k": "v"})

    assert event.meta == {"k": "v", "source": "cli"}
