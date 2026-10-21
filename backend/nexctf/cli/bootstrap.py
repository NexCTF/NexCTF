"""``manager bootstrap``: create the default admin from settings."""

lazy from sqlalchemy import func
lazy from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.cli.common import CliError, command, console
lazy from nexctf import crud
lazy from nexctf.api.scope import full_admin_scopes
lazy from nexctf.api.security import TOKEN_PREFIX, _hash_token, hash_password
lazy from nexctf.core.config import settings
lazy from nexctf.core.db import get_db_context
lazy from nexctf.model import User, UserRole, UserToken


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
        filters=[func.lower(User.username) == settings.DEFAULT_ADMIN_USERNAME.lower()],
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
                scopes=full_admin_scopes(),
            )
        )

    return True


@command
async def bootstrap_command() -> None:
    """Create the default admin account from settings if it does not exist."""
    try:
        async with get_db_context() as session:
            created = await create_default_admin(session)
    except ValueError as exc:
        raise CliError(str(exc)) from exc

    username = settings.DEFAULT_ADMIN_USERNAME
    if created:
        console.print(f"Created admin user {username!r}.")
    else:
        console.print(f"Admin user {username!r} already exists; skipping.")
