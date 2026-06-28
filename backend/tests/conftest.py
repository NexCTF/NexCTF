"""Pytest configuration for NexCTF backend tests."""

import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi_toolsets.pytest import (
    create_async_client,
    create_db_session,
    create_worker_database,
    register_fixtures,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ["NEXCTF_TEST_MODE"] = "1"

from nexctf.core.config import settings
from nexctf.core.db import db
from nexctf.core.cache import get_redis
from nexctf.fixtures import test_fixture_registry
from nexctf.main import app
from nexctf.model import Base, User, UserRole

register_fixtures(test_fixture_registry, globals())


@pytest.fixture
def mock_redis():
    """Mock Redis client with async publish support."""
    redis_mock = AsyncMock()
    redis_mock.publish = AsyncMock(return_value=1)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.getdel = AsyncMock(return_value=None)

    # pipeline() is a synchronous call returning a pipeline object whose
    # execute() is async.  results[2] is the zcard count; return 0 so the
    # sliding-window rate limiter never triggers during tests.
    _pipeline = MagicMock()
    _pipeline.execute = AsyncMock(return_value=[None, None, 0, None])
    redis_mock.pipeline = MagicMock(return_value=_pipeline)

    async def _empty_scan(*args, **kwargs):
        if False:
            yield

    redis_mock.scan_iter = _empty_scan
    return redis_mock


@pytest.fixture(scope="session")
async def worker_db_url():
    """Create and drop a per-worker test database."""
    async with create_worker_database(
        database_url=str(settings.SQLALCHEMY_DATABASE_URI),
        default_test_db="test",
    ) as url:
        yield url


@pytest.fixture
async def db_session(worker_db_url):
    """Yield a DB session with tables created and cleaned between tests."""
    async with create_db_session(
        database_url=worker_db_url, base=Base, cleanup=True
    ) as session:
        yield session


@pytest.fixture
def client_factory(db_session: AsyncSession, mock_redis):
    """Returns a context manager that creates an isolated AsyncClient with test overrides."""

    @asynccontextmanager
    async def _create() -> AsyncIterator[AsyncClient]:
        async def _db():
            yield db_session

        async def _redis():
            yield mock_redis

        async with create_async_client(
            app=app,
            base_url="http://127.0.0.1/api/v1",
            dependency_overrides={db: _db, get_redis: _redis},
        ) as c:
            yield c

    return _create


@pytest.fixture
async def http_client(client_factory) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated test client."""
    async with client_factory() as c:
        yield c


@pytest.fixture
def override_db_context(db_session: AsyncSession):
    """Patch get_db_context in security.py to reuse the test session.

    Functions like _verify_cookie() and create_api_token() call get_db_context()
    directly instead of using FastAPI dependency injection. Patching it in the
    security module namespace ensures they reuse the test session instead of
    opening a second connection on the same async task.
    """
    from nexctf.api import security

    original = security.get_db_context

    @asynccontextmanager
    async def _test_db_context():
        yield db_session

    security.get_db_context = _test_db_context
    try:
        yield
    finally:
        security.get_db_context = original


@asynccontextmanager
async def _role_client(
    client_factory,
    db_session: AsyncSession,
    username: str,
    password: str,
    role: UserRole,
) -> AsyncIterator[tuple[AsyncClient, User]]:
    """Create a logged-in AsyncClient for a user with the given role."""
    from nexctf.api.security import hash_password

    user = User(username=username, hashed_password=hash_password(password), role=role)
    db_session.add(user)
    await db_session.flush()

    async with client_factory() as c:
        resp = await c.post(
            "/auth/token", data={"username": username, "password": password}
        )
        assert resp.status_code == 204
        yield c, user


@pytest.fixture
async def admin_client(
    client_factory,
    db_session: AsyncSession,
    override_db_context,
) -> AsyncGenerator[tuple[AsyncClient, User], None]:
    """Authenticated client logged in as an admin user."""
    async with _role_client(
        client_factory, db_session, "test_admin", "adminpass", UserRole.admin
    ) as item:
        yield item


@pytest.fixture
async def moderator_client(
    client_factory,
    db_session: AsyncSession,
    override_db_context,
) -> AsyncGenerator[tuple[AsyncClient, User], None]:
    """Authenticated client logged in as a moderator user."""
    async with _role_client(
        client_factory,
        db_session,
        "test_moderator",
        "moderatorpass",
        UserRole.moderator,
    ) as item:
        yield item


@pytest.fixture
async def user_client(
    client_factory,
    db_session: AsyncSession,
    override_db_context,
) -> AsyncGenerator[tuple[AsyncClient, User], None]:
    """Authenticated client logged in as a regular user."""
    async with _role_client(
        client_factory, db_session, "test_user", "userpass", UserRole.user
    ) as item:
        yield item


@pytest.fixture(params=["admin", "moderator", "user"])
async def role_client(
    request,
    client_factory,
    db_session: AsyncSession,
    override_db_context,
) -> AsyncGenerator[tuple[AsyncClient, User], None]:
    """Parametrized fixture that runs tests once per role (admin, moderator, user)."""
    role_map = {
        "admin": UserRole.admin,
        "moderator": UserRole.moderator,
        "user": UserRole.user,
    }
    role = role_map[request.param]
    username = f"test_{request.param}"
    password = f"{request.param}pass"

    async with _role_client(
        client_factory, db_session, username, password, role
    ) as item:
        yield item
