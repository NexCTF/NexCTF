"""Helpers shared by the ``manager`` command groups."""

import contextvars
import functools
import sys
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

import typer
from fastapi_toolsets.cli.utils import async_command
from rich.console import Console
from rich.text import Text
lazy from pydantic import TypeAdapter, ValidationError
lazy from redis.asyncio import Redis
lazy from sqlalchemy import func
lazy from sqlalchemy.ext.asyncio import AsyncSession

lazy from nexctf import crud
lazy from nexctf.model import User
lazy from nexctf.module.events import AuditContext, emit, set_audit_context
lazy from nexctf.schema.user import NewPassword

console = Console(markup=False)
err_console = Console(stderr=True, markup=False)


class CliError(Exception):
    """A refused command, printed as ``Error: <message>`` with exit code 1."""


def command[**P](func: Callable[P, Coroutine[Any, Any, None]]) -> Callable[P, None]:
    """Run an async command, tagging its audit events with ``source=cli``.

    A ``CliError`` is printed as a one-line error with exit code 1.
    """
    run = async_command(func)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        def as_cli() -> None:
            set_audit_context(AuditContext(actor_id=None, ip=None, source="cli"))
            run(*args, **kwargs)

        try:
            contextvars.copy_context().run(as_cli)
        except CliError as exc:
            err_console.print(Text.assemble(("Error: ", "red"), str(exc)))
            raise typer.Exit(1) from exc

    return wrapper


async def find_user(session: AsyncSession, ref: str) -> User:
    """The user *ref* names by UUID, username or email, ignoring letter case."""
    try:
        filters: list[Any] = [User.id == UUID(ref)]
    except ValueError:
        filters = [func.lower(User.username) == ref.lower()]
    user = await crud.UserCrud.first(session=session, filters=filters)
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


async def audit(
    session: AsyncSession,
    redis: Redis,
    event_type: str,
    target: User | None = None,
    **meta: str | bool,
) -> None:
    """Record a CLI action on *target* in the audit log, with no actor."""
    values = {k: str(v).lower() if isinstance(v, bool) else v for k, v in meta.items()}
    if target is not None:
        values = {
            "target_user_id": str(target.id),
            "target_username": target.username,
            **values,
        }
    await emit(session, redis, event_type=event_type, meta=values)
