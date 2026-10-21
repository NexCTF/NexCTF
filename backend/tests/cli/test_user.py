"""Tests for ``manager user``: lookup, account recovery and their guards."""

from collections.abc import Awaitable
from functools import partial
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.api.security import hash_password, verify_password
from nexctf.cli import user as cli_user
from nexctf.cli.common import CliError, find_user
from nexctf.model import Event, User, UserRole, UserSession, UserToken
from tests.base import add_session, make_user


async def _add_token(db_session: AsyncSession, user: User) -> None:
    db_session.add(
        UserToken(user_id=user.id, token_hash=uuid4().hex, name="t", scopes=[])
    )
    await db_session.flush()


async def _sessions(db_session: AsyncSession, user: User) -> int:
    return await crud.UserSessionCrud.count(
        db_session, [UserSession.user_id == user.id]
    )


async def _tokens(db_session: AsyncSession, user: User) -> int:
    return await crud.UserTokenCrud.count(db_session, [UserToken.user_id == user.id])


async def _last_event(db_session: AsyncSession) -> Event:
    query = select(Event).order_by(Event.created_at.desc()).limit(1)
    return (await db_session.execute(query)).scalar_one()


@pytest.mark.parametrize("ref", ["Alice", "ALICE@example.com", "id"])
async def test_find_user_by_username_email_or_id(
    db_session: AsyncSession, ref: str
) -> None:
    """A user is found by any identifier, ignoring letter case."""
    alice = await make_user(db_session, "alice")
    alice.email = "alice@example.com"
    await db_session.flush()

    found = await find_user(db_session, str(alice.id) if ref == "id" else ref)

    assert found.id == alice.id


async def test_find_user_refuses_unknown(db_session: AsyncSession) -> None:
    with pytest.raises(CliError, match="No user matches"):
        await find_user(db_session, "ghost")


async def test_create_user_is_verified_and_audited(
    db_session: AsyncSession, mock_redis
) -> None:
    """A CLI-created admin has a verified email and a CLI audit event."""
    user = await cli_user.create_user(
        db_session,
        mock_redis,
        "carol",
        "long-enough-password",
        email="carol@example.com",
        admin=True,
    )

    assert user.role is UserRole.admin
    assert user.email_verified is True
    assert user.hashed_password is not None
    assert verify_password("long-enough-password", user.hashed_password)
    event = await _last_event(db_session)
    assert event.event_type == "admin.user_created"
    assert event.actor_id is None


@pytest.mark.parametrize(
    ("username", "password", "error"),
    [
        ("ALICE", "long-enough-password", "already taken"),
        ("dave", "short", "Invalid user"),
    ],
)
async def test_create_user_refusals(
    db_session: AsyncSession, mock_redis, username: str, password: str, error: str
) -> None:
    await make_user(db_session, "alice")

    with pytest.raises(CliError, match=error):
        await cli_user.create_user(
            db_session, mock_redis, username, password, email=None, admin=False
        )


async def test_promote_signs_the_user_out(db_session: AsyncSession, mock_redis) -> None:
    """Granting admin revokes every browser session, as the API does."""
    user = await make_user(db_session, "erin")
    await add_session(db_session, user, ip="203.0.113.1")

    await cli_user.set_role(db_session, mock_redis, user, UserRole.admin)

    await db_session.refresh(user)
    assert user.role is UserRole.admin
    assert await _sessions(db_session, user) == 0


@pytest.mark.parametrize(
    "disarm",
    [
        partial(cli_user.set_role, role=UserRole.user),
        partial(cli_user.set_active, active=False),
    ],
    ids=["demote", "deactivate"],
)
async def test_last_active_admin_is_kept(
    db_session: AsyncSession, mock_redis, disarm: partial[Awaitable[None]]
) -> None:
    """The only active admin can be neither demoted nor deactivated."""
    admin = await make_user(db_session, "root", role=UserRole.admin)
    retired = await make_user(db_session, "retired", role=UserRole.admin)
    retired.is_active = False
    await db_session.flush()

    with pytest.raises(CliError, match="last active admin"):
        await disarm(db_session, mock_redis, admin)


async def test_demote_with_another_admin(db_session: AsyncSession, mock_redis) -> None:
    admin = await make_user(db_session, "root", role=UserRole.admin)
    await make_user(db_session, "backup", role=UserRole.admin)

    await cli_user.set_role(db_session, mock_redis, admin, UserRole.user)

    await db_session.refresh(admin)
    assert admin.role is UserRole.user


async def test_set_password_revokes_access(
    db_session: AsyncSession, mock_redis
) -> None:
    """A new password voids sessions, API tokens and earlier reset links."""
    user = await make_user(db_session, "frank")
    user.hashed_password = hash_password("old-password-1")
    await db_session.flush()
    await add_session(db_session, user, ip="203.0.113.2")
    await _add_token(db_session, user)
    version = user.session_version

    await cli_user.set_password(db_session, mock_redis, user, "new-password-1")

    await db_session.refresh(user)
    assert user.hashed_password is not None
    assert verify_password("new-password-1", user.hashed_password)
    assert user.session_version == version + 1
    assert await _sessions(db_session, user) == 0
    assert await _tokens(db_session, user) == 0


async def test_reset_link_points_at_the_frontend(
    db_session: AsyncSession, mock_redis
) -> None:
    user = await make_user(db_session, "gina")

    link = await cli_user.issue_reset_link(db_session, mock_redis, user)

    assert "/reset-password?token=" in link
    mock_redis.set.assert_awaited_once()


async def test_disable_totp(db_session: AsyncSession, mock_redis) -> None:
    user = await make_user(db_session, "hank")
    user.totp_secret = "JBSWY3DPEHPK3PXP"
    await db_session.flush()

    await cli_user.disable_totp(db_session, mock_redis, user)

    await db_session.refresh(user)
    assert user.totp_secret is None
    with pytest.raises(CliError, match="no 2FA"):
        await cli_user.disable_totp(db_session, mock_redis, user)


async def test_verify_email(db_session: AsyncSession, mock_redis) -> None:
    user = await make_user(db_session, "ivy")
    with pytest.raises(CliError, match="no email"):
        await cli_user.verify_email(db_session, mock_redis, user)
    user.email = "ivy@example.com"
    await db_session.flush()

    await cli_user.verify_email(db_session, mock_redis, user)

    await db_session.refresh(user)
    assert user.email_verified is True


@pytest.mark.parametrize(("tokens", "tokens_left"), [(False, 1), (True, 0)])
async def test_sign_out(
    db_session: AsyncSession, mock_redis, tokens: bool, tokens_left: int
) -> None:
    """Sessions always go; API tokens only with ``--tokens``."""
    user = await make_user(db_session, "jack")
    await add_session(db_session, user, ip="203.0.113.3")
    await _add_token(db_session, user)

    await cli_user.sign_out(db_session, mock_redis, user, tokens=tokens)

    assert await _sessions(db_session, user) == 0
    assert await _tokens(db_session, user) == tokens_left


async def test_sign_out_everyone(db_session: AsyncSession, mock_redis) -> None:
    kim = await make_user(db_session, "kim")
    lee = await make_user(db_session, "lee")
    for user in (kim, kim, lee):
        await add_session(db_session, user, ip="203.0.113.4")

    assert await cli_user.sign_out_everyone(db_session, mock_redis) == 2
    assert await db_session.scalar(select(func.count()).select_from(UserSession)) == 0
