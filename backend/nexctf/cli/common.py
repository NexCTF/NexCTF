"""Helpers shared by the ``manager`` command groups."""

import functools
import importlib
import logging
import sys
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

import typer
from fastapi_toolsets.cli.utils import async_command
from rich.console import Console
from rich.text import Text
lazy from pydantic import TypeAdapter, ValidationError
lazy from sqlalchemy import func
lazy from sqlalchemy.ext.asyncio import AsyncSession

lazy from nexctf import crud
lazy from nexctf.model import User
lazy from nexctf.module.events import AuditContext, set_audit_context
lazy from nexctf.plugins import load_plugin_registries
lazy from nexctf.schema.user import NewPassword

console = Console(markup=False)
err_console = Console(stderr=True, markup=False)


class CliError(Exception):
    """A refused command, printed as ``Error: <message>`` with exit code 1."""


def load_registries() -> None:
    """Register the core and plugin config keys, as the app does at startup."""
    importlib.import_module("nexctf.settings")
    logging.getLogger("nexctf.plugins.loader").setLevel(logging.WARNING)
    load_plugin_registries()


def command[**P](func: Callable[P, Coroutine[Any, Any, None]]) -> Callable[P, None]:
    """Run an async command, tagging its audit events with ``source=cli``.

    A ``CliError`` is printed as a one-line error with exit code 1.
    """

    @functools.wraps(func)
    async def as_cli(*args: P.args, **kwargs: P.kwargs) -> None:
        set_audit_context(AuditContext(actor_id=None, ip=None, source="cli"))
        await func(*args, **kwargs)

    run = async_command(as_cli)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            run(*args, **kwargs)
        except CliError as exc:
            err_console.print(Text.assemble(("Error: ", "red"), str(exc)))
            raise typer.Exit(1) from exc

    return wrapper


async def find_user(session: AsyncSession, ref: str) -> User:
    """The user *ref* names by UUID, username or email, ignoring letter case."""
    user = None
    try:
        user = await crud.UserCrud.first(
            session=session, filters=[User.id == UUID(ref)]
        )
    except ValueError:
        pass
    if user is None:
        user = await crud.UserCrud.first(
            session=session, filters=[func.lower(User.username) == ref.lower()]
        )
    if user is None and "@" in ref:
        user = await crud.UserCrud.first(
            session=session, filters=[func.lower(User.email) == ref.lower()]
        )
    if user is None:
        raise CliError(f"No user matches {ref!r}")
    return user


def read_password(from_stdin: bool) -> str:
    """Read a new password from stdin or a hidden, confirmed prompt."""
    if from_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = typer.prompt(
            "New password", hide_input=True, confirmation_prompt=True
        )
    try:
        return TypeAdapter(NewPassword).validate_python(password)
    except ValidationError as exc:
        raise CliError(f"Invalid password: {exc.errors()[0]['msg']}") from exc
