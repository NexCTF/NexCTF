"""Custom ``manager`` CLI commands for NexCTF.

Registered as the toolsets ``custom_cli`` (see ``[tool.fastapi-toolsets]`` in
``pyproject.toml``); the built-in ``fixtures`` group is attached on top of it.
"""

import typer

from nexctf.cli.backup import backup_cli
from nexctf.cli.bootstrap import bootstrap_command
from nexctf.cli.config import config_cli
from nexctf.cli.ratelimit import ratelimit_cli
from nexctf.cli.user import user_cli

cli = typer.Typer(
    name="manager",
    help="CLI utilities for NexCTF.",
    no_args_is_help=True,
)
cli.command("bootstrap")(bootstrap_command)
cli.add_typer(user_cli, name="user")
cli.add_typer(config_cli, name="config")
cli.add_typer(backup_cli, name="backup")
cli.add_typer(ratelimit_cli, name="ratelimit")
