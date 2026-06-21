"""Custom ``manager`` CLI commands for NexCTF.

Registered as the toolsets ``custom_cli`` (see ``[tool.fastapi-toolsets]`` in
``pyproject.toml``); the built-in ``fixtures`` group is attached on top of it.
"""

import typer
from fastapi_toolsets.cli.utils import async_command
from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

import nexctf.crud as crud
from nexctf.api.security import TOKEN_PREFIX, _hash_token, hash_password
from nexctf.core.config import settings
from nexctf.core.db import get_db_context
from nexctf.model import User, UserRole, UserToken

cli = typer.Typer(
    name="manager",
    help="CLI utilities for NexCTF.",
    no_args_is_help=True,
)
console = Console()


async def create_default_admin(session: AsyncSession) -> bool:
    """Create the default admin account and API token if it does not exist."""
    token = settings.DEFAULT_ADMIN_TOKEN
    if token and not token.startswith(TOKEN_PREFIX):
        raise ValueError(
            f"DEFAULT_ADMIN_TOKEN must start with {TOKEN_PREFIX!r} to be a valid "
            "bearer token."
        )

    existing = await crud.UserCrud.first(
        session=session,
        filters=[User.username == settings.DEFAULT_ADMIN_USERNAME],
    )
    if existing is not None:
        return False

    admin = User(
        username=settings.DEFAULT_ADMIN_USERNAME,
        hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
        role=UserRole.admin,
    )
    session.add(admin)
    await session.flush()

    if token:
        session.add(
            UserToken(
                user_id=admin.id,
                token_hash=_hash_token(token),
                name="default",
            )
        )

    return True


@cli.command("create-admin")
@async_command
async def create_admin() -> None:
    """Create the default admin account from settings if it does not exist."""
    try:
        async with get_db_context() as session:
            created = await create_default_admin(session)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    username = settings.DEFAULT_ADMIN_USERNAME
    if created:
        console.print(f"Created admin user {username!r}.")
    else:
        console.print(f"Admin user {username!r} already exists; skipping.")
