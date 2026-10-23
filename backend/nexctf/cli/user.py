"""``manager user``: inspect and recover user accounts."""

from collections.abc import Awaitable, Callable, Sequence
from functools import partial
from typing import Annotated

import typer
from rich.table import Table
from rich.text import Text
lazy from fastapi_toolsets.exceptions import ConflictError
lazy from pydantic import ValidationError
lazy from redis.asyncio import Redis
lazy from sqlalchemy import delete, or_, select
lazy from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.cli.common import (
    CliError,
    audit,
    command,
    console,
    find_user,
    read_password,
)
lazy from nexctf import crud
lazy from nexctf.api.security import (
    hash_password,
    issue_password_reset_token,
    password_reset_link,
)
lazy from nexctf.core.cache import get_client as get_redis_client
lazy from nexctf.core.db import get_db_context
lazy from nexctf.core.eventbus import (
    close_user_streams,
    publish_event,
    user_stream_channel,
)
lazy from nexctf.model import OAuthAccount, User, UserRole, UserSession, UserToken
lazy from nexctf.module.session import (
    replace_password,
    revoke_all_access,
    revoke_user_sessions,
)
lazy from nexctf.module.user import create_verified_user, reset_totp
lazy from nexctf.schema.user import (
    AdminUserCreate,
    AdminUserUpdate,
    UserEmailVerifiedUpdate,
)
lazy from nexctf.util.sql import count_of

user_cli = typer.Typer(help="Inspect and recover user accounts.", no_args_is_help=True)

UserArg = Annotated[str, typer.Argument(help="Username, email or UUID.")]
PasswordStdin = Annotated[
    bool, typer.Option("--password-stdin", help="Read the password from stdin.")
]


async def list_users(
    session: AsyncSession, *, admins: bool, search: str | None, limit: int
) -> Sequence[User]:
    """Users by username, optionally only admins or those matching *search*."""
    filters = []
    if admins:
        filters.append(User.role == UserRole.admin)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(User.username.ilike(pattern), User.email.ilike(pattern)))
    return await crud.UserCrud.get_multi(
        session=session, filters=filters, order_by=User.username, limit=limit
    )


async def create_user(
    session: AsyncSession,
    redis: Redis,
    username: str,
    password: str,
    *,
    email: str | None,
    admin: bool,
) -> User:
    """Create a user with a verified email, as the admin API does."""
    try:
        obj = AdminUserCreate(
            username=username,
            password=password,
            email=email,
            role=UserRole.admin if admin else UserRole.user,
        )
    except ValidationError as exc:
        raise CliError(f"Invalid user: {exc.errors()[0]['msg']}") from exc
    try:
        return await create_verified_user(session, redis, obj)
    except ConflictError as exc:
        raise CliError(str(exc)) from exc


async def set_role(
    session: AsyncSession, redis: Redis, user: User, role: UserRole
) -> None:
    """Change the role; granting admin signs the user out everywhere."""
    if user.role is role:
        raise CliError(f"{user.username!r} is already {role.value}")
    granting_admin = role is UserRole.admin
    if not granting_admin:
        await _require_other_admin(session, user)
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=AdminUserUpdate(id=user.id, role=role),
    )
    if granting_admin:
        await revoke_user_sessions(session, user)
    await close_user_streams(redis, user.id)
    await audit(
        session,
        redis,
        "admin.user_updated",
        user,
        role=role.value,
        sessions_revoked=granting_admin,
    )


async def set_active(
    session: AsyncSession, redis: Redis, user: User, active: bool
) -> None:
    """Activate or deactivate an account."""
    if user.is_active is active:
        state = "active" if active else "inactive"
        raise CliError(f"{user.username!r} is already {state}")
    if not active:
        await _require_other_admin(session, user)
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=AdminUserUpdate(id=user.id, is_active=active),
    )
    await close_user_streams(redis, user.id)
    await audit(session, redis, "admin.user_updated", user, is_active=active)


async def set_password(
    session: AsyncSession, redis: Redis, user: User, password: str
) -> None:
    """Replace the password, revoking every session and API token."""
    await replace_password(session, user, hash_password(password))
    await close_user_streams(redis, user.id)
    await audit(session, redis, "admin.user_password_set", user)


async def issue_reset_link(session: AsyncSession, redis: Redis, user: User) -> str:
    """A single-use password reset link, valid for one hour."""
    token = await issue_password_reset_token(redis, user)
    await audit(session, redis, "admin.user_password_reset_token", user)
    return password_reset_link(token)


async def disable_totp(session: AsyncSession, redis: Redis, user: User) -> None:
    """Clear the user's TOTP secret."""
    if not user.totp_secret:
        raise CliError(f"{user.username!r} has no 2FA enabled")
    await reset_totp(session, redis, user)


async def verify_email(session: AsyncSession, redis: Redis, user: User) -> None:
    """Mark the user's email as verified."""
    if not user.email:
        raise CliError(f"{user.username!r} has no email")
    if user.email_verified:
        raise CliError(f"{user.username!r} already has a verified email")
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserEmailVerifiedUpdate(id=user.id, email_verified=True),
    )
    await audit(session, redis, "admin.user_updated", user, email_verified=True)


async def sign_out(
    session: AsyncSession, redis: Redis, user: User, *, tokens: bool
) -> None:
    """Revoke the user's sessions, and their API tokens with *tokens*."""
    if tokens:
        await revoke_all_access(session, user)
    else:
        await revoke_user_sessions(session, user)
    await close_user_streams(redis, user.id)
    await audit(
        session, redis, "admin.user_sessions_revoked", user, tokens_revoked=tokens
    )


async def sign_out_everyone(session: AsyncSession, redis: Redis) -> int:
    """Revoke every browser session, returning how many users were signed out."""
    deleted = await session.scalars(delete(UserSession).returning(UserSession.user_id))
    signed_out = set(deleted.all())
    await publish_event(redis, [user_stream_channel(u) for u in signed_out], "")
    await audit(
        session, redis, "admin.sessions_revoked_all", users=str(len(signed_out))
    )
    return len(signed_out)


async def _require_other_admin(session: AsyncSession, user: User) -> None:
    """Refuse to disarm the last active admin."""
    if user.role is not UserRole.admin or not user.is_active:
        return
    others = await crud.UserCrud.count(
        session,
        [User.role == UserRole.admin, User.is_active.is_(True), User.id != user.id],
    )
    if not others:
        raise CliError(f"{user.username!r} is the last active admin")


async def _apply(
    ref: str, action: Callable[[AsyncSession, Redis, User], Awaitable[None]]
) -> User:
    """Find the user *ref* names and apply *action* to them."""
    async with get_db_context() as session:
        target = await find_user(session, ref)
        await action(session, get_redis_client(), target)
    return target


@user_cli.command("list")
@command
async def list_command(
    admins: Annotated[bool, typer.Option("--admins", help="Only admins.")] = False,
    search: Annotated[
        str | None, typer.Option(help="Match part of a username or email.")
    ] = None,
    limit: Annotated[int, typer.Option(help="Maximum rows to show.")] = 50,
) -> None:
    """List users."""
    async with get_db_context() as session:
        users = await list_users(session, admins=admins, search=search, limit=limit)
    table = Table("Username", "Email", "Role", "Active", "2FA", "Team")
    for user in users:
        table.add_row(
            user.username,
            user.email or "",
            user.role.value,
            _yes(user.is_active),
            _yes(bool(user.totp_secret)),
            user.team.name if user.team else "",
        )
    console.print(table)


@user_cli.command("show")
@command
async def show_command(user: UserArg) -> None:
    """Show one user's account and access."""
    async with get_db_context() as session:
        target = await find_user(session, user)
        sessions, tokens, providers = (
            await session.execute(
                select(
                    count_of(UserSession, UserSession.user_id == target.id),
                    count_of(UserToken, UserToken.user_id == target.id),
                    count_of(OAuthAccount, OAuthAccount.user_id == target.id),
                )
            )
        ).one()
    email = target.email or "-"
    if target.email:
        email += " (verified)" if target.email_verified else " (unverified)"
    table = Table(show_header=False, box=None)
    for label, value in (
        ("ID", str(target.id)),
        ("Username", target.username),
        ("Email", email),
        ("Role", target.role.value),
        ("Active", _yes(target.is_active)),
        ("Password", _yes(bool(target.hashed_password))),
        ("2FA", _yes(bool(target.totp_secret))),
        ("Team", target.team.name if target.team else "-"),
        ("Linked providers", str(providers)),
        ("Sessions", str(sessions)),
        ("API tokens", str(tokens)),
    ):
        table.add_row(Text(label, style="bold"), value)
    console.print(table)


@user_cli.command("create")
@command
async def create_command(
    username: Annotated[str, typer.Argument(help="Username of the new account.")],
    email: Annotated[str | None, typer.Option(help="Email, marked verified.")] = None,
    admin: Annotated[bool, typer.Option("--admin", help="Create an admin.")] = False,
    password_stdin: PasswordStdin = False,
) -> None:
    """Create a user, prompting for the password."""
    password = read_password(password_stdin)
    async with get_db_context() as session:
        await create_user(
            session, get_redis_client(), username, password, email=email, admin=admin
        )
    console.print(f"Created {'admin' if admin else 'user'} {username!r}.")


@user_cli.command("promote")
@command
async def promote_command(user: UserArg) -> None:
    """Grant admin and sign the user out everywhere."""
    target = await _apply(user, partial(set_role, role=UserRole.admin))
    console.print(f"{target.username!r} is now an admin and was signed out.")


@user_cli.command("demote")
@command
async def demote_command(user: UserArg) -> None:
    """Remove admin, refusing the last active admin."""
    target = await _apply(user, partial(set_role, role=UserRole.user))
    console.print(f"{target.username!r} is no longer an admin.")


@user_cli.command("activate")
@command
async def activate_command(user: UserArg) -> None:
    """Re-enable a deactivated account."""
    target = await _apply(user, partial(set_active, active=True))
    console.print(f"Activated {target.username!r}.")


@user_cli.command("deactivate")
@command
async def deactivate_command(user: UserArg) -> None:
    """Disable an account, refusing the last active admin."""
    target = await _apply(user, partial(set_active, active=False))
    console.print(f"Deactivated {target.username!r}.")


@user_cli.command("reset-password")
@command
async def reset_password_command(
    user: UserArg,
    link: Annotated[
        bool, typer.Option("--link", help="Print a one-hour reset link instead.")
    ] = False,
    password_stdin: PasswordStdin = False,
) -> None:
    """Set a new password, or print a reset link, signing the user out."""
    if link:
        async with get_db_context() as session:
            target = await find_user(session, user)
            url = await issue_reset_link(session, get_redis_client(), target)
        console.print(url, soft_wrap=True)
        return
    password = read_password(password_stdin)
    target = await _apply(user, partial(set_password, password=password))
    console.print(
        f"Password of {target.username!r} replaced; sessions and API tokens "
        "were revoked."
    )


@user_cli.command("disable-2fa")
@command
async def disable_2fa_command(user: UserArg) -> None:
    """Turn off the user's 2FA."""
    target = await _apply(user, disable_totp)
    console.print(f"Disabled 2FA for {target.username!r}.")


@user_cli.command("verify-email")
@command
async def verify_email_command(user: UserArg) -> None:
    """Mark the user's email as verified."""
    target = await _apply(user, verify_email)
    console.print(f"Verified the email of {target.username!r}.")


@user_cli.command("sign-out")
@command
async def sign_out_command(
    user: Annotated[
        str | None, typer.Argument(help="Username, email or UUID.", show_default=False)
    ] = None,
    everyone: Annotated[
        bool, typer.Option("--all", help="Sign out every user.")
    ] = False,
    tokens: Annotated[
        bool, typer.Option("--tokens", help="Revoke the user's API tokens too.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip the confirmation.")
    ] = False,
) -> None:
    """Sign one user, or everyone with --all, out of every browser session."""
    if everyone == (user is not None):
        raise CliError("Pass either a user or --all")
    if everyone and tokens:
        raise CliError("--tokens needs a user")
    if user is None:
        if not yes:
            typer.confirm("Sign every user out of every browser session?", abort=True)
        async with get_db_context() as session:
            count = await sign_out_everyone(session, get_redis_client())
        console.print(f"Signed out {count} user(s).")
        return
    target = await _apply(user, partial(sign_out, tokens=tokens))
    revoked = "sessions and API tokens" if tokens else "sessions"
    console.print(f"Revoked the {revoked} of {target.username!r}.")


def _yes(value: bool) -> str:
    return "yes" if value else "no"
