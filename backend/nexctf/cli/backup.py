"""``manager backup``: list, create and restore database dumps in S3."""

from typing import Annotated

import typer
from rich.table import Table

from nexctf.cli.common import CliError, command, console
lazy from nexctf.core.cache import get_client as get_redis_client
lazy from nexctf.core.db import get_db_context
lazy from nexctf.module import backup
lazy from nexctf.module.events import emit
lazy from nexctf.schema.backup import BackupSource

backup_cli = typer.Typer(help="List, create and restore backups.", no_args_is_help=True)


@backup_cli.command("list")
@command
async def list_command() -> None:
    """List backups, newest first."""
    table = Table("Key", "Size", "Created", "Revision", "Source")
    for item in await backup.listing():
        table.add_row(
            item["key"],
            _size(item["size"]),
            item["created_at"].strftime("%Y-%m-%d %H:%M:%S %Z"),
            item["revision"] or "-",
            item["source"].value if item["source"] else "-",
        )
    console.print(table)


@backup_cli.command("create")
@command
async def create_command() -> None:
    """Dump the database to S3 now."""
    try:
        key, size = await backup.create(BackupSource.MANUAL)
    except backup.BackupError as exc:
        raise CliError(str(exc)) from exc
    async with get_db_context() as session:
        await emit(
            session,
            get_redis_client(),
            event_type="backup.created",
            target_type="backup",
            target_label=key,
        )
    console.print(f"Created {key!r} ({_size(size)}).")


@backup_cli.command("restore")
@command
async def restore_command(
    key: str,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip the confirmation.")
    ] = False,
) -> None:
    """Replace the database with a backup from S3. Stop the app before running."""
    if not yes:
        typer.confirm(
            f"Restore {key}? This overwrites the current database and logs out "
            "every user. The current database is dumped to S3 first.",
            abort=True,
        )

    try:
        await backup.restore(key)
    except backup.BackupError as exc:
        raise CliError(str(exc)) from exc

    # Drop every cached structure describing the replaced database.
    await get_redis_client().flushdb()

    console.print(f"Restored {key!r}. Restart the backend and worker.")


def _size(size: int) -> str:
    """*size* bytes in a human-readable unit."""
    if size < 1024:
        return f"{size} B"
    value = size / 1024
    for unit in ("KiB", "MiB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"
