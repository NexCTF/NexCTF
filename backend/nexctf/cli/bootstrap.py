"""``manager bootstrap``: create the default admin, or open the first-run setup."""

from typing import Annotated

import typer
lazy from sqlalchemy import func
lazy from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.cli.common import CliError, command, console
lazy from nexctf import crud
lazy from nexctf.api.scope import full_admin_scopes
lazy from nexctf.api.security import TOKEN_PREFIX, _hash_token, hash_password
lazy from nexctf.core.cache import get_client as get_redis_client
lazy from nexctf.core.config import settings
lazy from nexctf.core.db import get_db_context
lazy from nexctf.model import User, UserRole, UserToken
lazy from nexctf.module.setup import (
    admin_exists,
    consume_setup_token,
    issue_setup_token,
    setup_link,
)


async def create_default_admin(session: AsyncSession) -> bool:
    """Create the admin and API token from settings when a password is set."""
    password = settings.DEFAULT_ADMIN_PASSWORD
    token = settings.DEFAULT_ADMIN_TOKEN
    if token and not token.startswith(TOKEN_PREFIX):
        raise ValueError(
            f"DEFAULT_ADMIN_TOKEN must start with {TOKEN_PREFIX!r} to be a valid "
            "bearer token."
        )

    if await admin_exists(session):
        return False
    if not password:
        if token:
            raise ValueError("DEFAULT_ADMIN_TOKEN requires DEFAULT_ADMIN_PASSWORD.")
        return False
    taken = await crud.UserCrud.first(
        session=session,
        filters=[func.lower(User.username) == settings.DEFAULT_ADMIN_USERNAME.lower()],
    )
    if taken is not None:
        console.print(
            f"User {taken.username!r} exists but is not an admin; "
            "skipping the default admin."
        )
        return False

    admin = User(
        username=settings.DEFAULT_ADMIN_USERNAME,
        hashed_password=hash_password(password),
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
                scopes=full_admin_scopes(),
            )
        )

    return True


@command
async def bootstrap_command(
    new_link: Annotated[
        bool,
        typer.Option("--new-link", help="Replace the setup link already issued."),
    ] = False,
) -> None:
    """Create the default admin from settings, else print a first-run setup link."""
    redis = get_redis_client()
    try:
        async with get_db_context() as session:
            created = await create_default_admin(session)
            has_admin = created or await admin_exists(session)
    except ValueError as exc:
        raise CliError(str(exc)) from exc

    if has_admin:
        await consume_setup_token(redis)
        if created:
            console.print(f"Created admin user {settings.DEFAULT_ADMIN_USERNAME!r}.")
        else:
            console.print("An admin account exists; first-run setup is closed.")
        return
    token = await issue_setup_token(redis, replace=new_link)
    if token is None:
        console.print(
            "No admin account yet. A setup link was already printed; run "
            "`manager bootstrap --new-link` to replace it."
        )
        return
    console.print(
        "No admin account yet. Create one from this one-time setup link:\n"
        f"\n    {setup_link(token)}\n\n"
        "Run `manager bootstrap --new-link` to replace it.",
        soft_wrap=True,
    )
