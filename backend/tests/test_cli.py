"""Tests for the custom ``manager`` CLI logic (create-admin)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.security import _hash_token, verify_password
from nexctf.cli import create_default_admin
from nexctf.core.config import settings
from nexctf.model import User, UserRole, UserToken


@pytest.fixture
def admin_settings(monkeypatch):
    """Configure deterministic default-admin settings for a test."""
    monkeypatch.setattr(settings, "DEFAULT_ADMIN_USERNAME", "seed_admin")
    monkeypatch.setattr(settings, "DEFAULT_ADMIN_PASSWORD", "seed_password")
    monkeypatch.setattr(settings, "DEFAULT_ADMIN_TOKEN", "nexctf_seed_token")


async def _get_admin(session: AsyncSession) -> User | None:
    return (
        await session.execute(select(User).where(User.username == "seed_admin"))
    ).scalar_one_or_none()


async def test_creates_admin_with_token(
    db_session: AsyncSession, admin_settings
) -> None:
    """A fresh database gets an admin user plus a usable API token."""
    created = await create_default_admin(db_session)
    assert created is True

    admin = await _get_admin(db_session)
    assert admin is not None
    # Role must be admin: the whole point is an account with full privileges.
    assert admin.role is UserRole.admin
    # Password is stored hashed, not in plaintext, and verifies.
    assert admin.hashed_password is not None
    assert admin.hashed_password != "seed_password"
    assert verify_password("seed_password", admin.hashed_password)

    token = (
        await db_session.execute(select(UserToken).where(UserToken.user_id == admin.id))
    ).scalar_one()
    # Token is stored as a hash that matches the configured raw token, so the
    # configured value authenticates against the bearer source.
    assert token.token_hash == _hash_token("nexctf_seed_token")


async def test_is_idempotent(db_session: AsyncSession, admin_settings) -> None:
    """Running twice neither duplicates the user nor errors."""
    assert await create_default_admin(db_session) is True
    assert await create_default_admin(db_session) is False

    users = (
        (await db_session.execute(select(User).where(User.username == "seed_admin")))
        .scalars()
        .all()
    )
    assert len(users) == 1


async def test_no_token_creates_user_without_token(
    db_session: AsyncSession, admin_settings, monkeypatch
) -> None:
    """When no token is configured the admin is created with no API token."""
    monkeypatch.setattr(settings, "DEFAULT_ADMIN_TOKEN", None)

    assert await create_default_admin(db_session) is True

    admin = await _get_admin(db_session)
    assert admin is not None
    tokens = (
        (
            await db_session.execute(
                select(UserToken).where(UserToken.user_id == admin.id)
            )
        )
        .scalars()
        .all()
    )
    assert tokens == []


async def test_rejects_token_without_prefix(
    db_session: AsyncSession, admin_settings, monkeypatch
) -> None:
    """A token missing the bearer prefix is rejected loudly, before any write."""
    monkeypatch.setattr(settings, "DEFAULT_ADMIN_TOKEN", "bad_token")

    with pytest.raises(ValueError, match="nexctf_"):
        await create_default_admin(db_session)

    assert await _get_admin(db_session) is None
