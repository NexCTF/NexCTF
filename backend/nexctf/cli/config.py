"""``manager config``: read and fix settings without the admin UI."""

from collections.abc import Awaitable, Callable
from typing import Annotated

import typer
from rich.table import Table
lazy from redis.asyncio import Redis
lazy from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.cli.common import CliError, command, console, load_registries
lazy from nexctf.core import appconfig
lazy from nexctf.core.cache import get_client as get_redis_client
lazy from nexctf.core.db import get_db_context
lazy from nexctf.exceptions import ConfigValidationError
lazy from nexctf.module.config import masked_value, reset_config, save_config

type ConfigWrite = Callable[
    [AsyncSession, Redis, dict[str, str]], Awaitable[dict[str, str]]
]

config_cli = typer.Typer(
    help="Read and fix settings without the admin UI.",
    no_args_is_help=True,
)


def describe(key: str, overrides: dict[str, str]) -> tuple[str, str]:
    """The value *key* resolves to, secrets masked, and where it comes from."""
    if key in overrides:
        source = "stored"
    elif appconfig.baseline_raw(key) != appconfig.get_def(key).default:
        source = "env"
    else:
        source = "default"
    value = masked_value(key, overrides)
    return str(value).lower() if isinstance(value, bool) else str(value), source


@config_cli.command("get")
@command
async def get_command(
    key: Annotated[
        str | None, typer.Argument(help="Setting key; all settings when omitted.")
    ] = None,
) -> None:
    """Show a setting, or every setting, with where its value comes from."""
    load_registries()
    keys = sorted(appconfig.all_defs()) if key is None else [key]
    if key is not None and key not in appconfig.all_defs():
        raise CliError(f"Unknown key: {key!r}")
    async with get_db_context() as session:
        overrides = await appconfig.stored_overrides(session)
    table = Table("Key", "Value", "Source")
    for name in keys:
        table.add_row(name, *describe(name, overrides))
    console.print(table)


@config_cli.command("set")
@command
async def set_command(
    key: Annotated[str, typer.Argument(help="Setting key.")],
    value: Annotated[str, typer.Argument(help="New value, as the API takes it.")],
) -> None:
    """Store a setting, validated as in the admin UI."""
    load_registries()
    new = await _write(lambda s, r, old: save_config(s, r, {key: value}, old))
    console.print(f"{key} = {describe(key, new)[0]}")


@config_cli.command("reset")
@command
async def reset_command(
    keys: Annotated[list[str], typer.Argument(help="Setting keys.")],
) -> None:
    """Drop stored settings so they fall back to the environment or the default."""
    load_registries()
    new = await _write(lambda s, r, old: reset_config(s, r, keys, old))
    for key in keys:
        value, source = describe(key, new)
        console.print(f"{key} = {value} ({source})")


async def _write(write: ConfigWrite) -> dict[str, str]:
    """Apply a config *write* over the stored values, mapping validation errors."""
    async with get_db_context() as session:
        old = await appconfig.stored_overrides(session)
        try:
            return await write(session, get_redis_client(), old)
        except ConfigValidationError as exc:
            raise CliError(str(exc.api_error.desc)) from exc
