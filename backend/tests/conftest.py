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
from pgqueuer import Queries
from pgqueuer.db import AsyncpgDriver
from sqlalchemy.ext.asyncio import AsyncSession

os.environ["NEXCTF_TEST_MODE"] = "1"

from nexctf.core import appconfig
from nexctf.core.cache import get_redis
from nexctf.core.config import settings
from nexctf.core.db import db
from nexctf.fixtures import test_fixture_registry
from nexctf.main import app
from nexctf.model import Base, User, UserRole
from nexctf.plugins import load_builtin_plugins
from nexctf.plugins.frontend import frontend_registry
from nexctf.plugins.registry import (
    challenge_registry,
    scheduler_registry,
    solution_registry,
    task_registry,
)
from nexctf.plugins.routes import route_registry
from nexctf.tasks.queue import DB_SETTINGS, build_queries, connect

register_fixtures(test_fixture_registry, globals())
# The test app skips the lifespan that loads plugins.
load_builtin_plugins()


@pytest.fixture
def isolated_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the test its own copy of every plugin registry and of config state."""
    for reg in (challenge_registry, solution_registry, scheduler_registry):
        monkeypatch.setattr(reg, "_entries", dict(reg._entries))
        monkeypatch.setattr(reg, "_owners", dict(reg._owners))
    for reg in (challenge_registry, solution_registry):
        monkeypatch.setattr(
            reg, "_polymorphic_subclasses", dict(reg._polymorphic_subclasses)
        )
    monkeypatch.setattr(task_registry, "_names", dict(task_registry._names))
    monkeypatch.setattr(route_registry, "_entries", {})
    monkeypatch.setattr(frontend_registry, "_entries", {})
    monkeypatch.setattr(appconfig, "_DEFS", dict(appconfig._DEFS))
    monkeypatch.setattr(appconfig, "_CATEGORIES", dict(appconfig._CATEGORIES))


@pytest.fixture
def config_overrides() -> dict[str, str]:
    """Config overrides the app reads for this test, as Redis would serve them."""
    return {}


@pytest.fixture
def mock_redis(config_overrides: dict[str, str]):
    """Mock Redis client with async publish support."""
    redis_mock = AsyncMock()
    redis_mock.publish = AsyncMock(return_value=1)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.getdel = AsyncMock(return_value=None)

    redis_mock.hgetall = AsyncMock(return_value=config_overrides)

    # pipeline() is a synchronous call returning a pipeline object whose
    # execute() is async.  results[2] is the zcard count; return 0 so the
    # sliding-window rate limiter never triggers during tests.
    _pipeline = MagicMock()
    _pipeline.execute = AsyncMock(return_value=[None, None, 0, None])
    redis_mock.pipeline = MagicMock(return_value=_pipeline)

    redis_mock.sunion = AsyncMock(return_value=set())
    return redis_mock


@pytest.fixture(scope="session")
async def worker_db_url():
    """Create and drop a per-worker test database."""
    async with create_worker_database(
        database_url=str(settings.SQLALCHEMY_DATABASE_URI),
        default_test_db="test",
    ) as url:
        yield url


@pytest.fixture(scope="session")
async def task_queue_schema(worker_db_url: str) -> str:
    """Install the task queue schema once in the per-worker test database."""
    conn = await connect(worker_db_url)
    try:
        queries = build_queries(AsyncpgDriver(conn))
        if not await queries.has_table(DB_SETTINGS.queue_table):
            await queries.install()
    finally:
        await conn.close()
    return worker_db_url


@pytest.fixture
async def task_queue(task_queue_schema: str) -> AsyncIterator[Queries]:
    """Yield queries on a task queue emptied before the test."""
    conn = await connect(task_queue_schema)
    queries = build_queries(AsyncpgDriver(conn))
    await queries.clear_queue()
    await queries.clear_schedule()
    try:
        yield queries
    finally:
        await conn.close()


@pytest.fixture
async def db_session(worker_db_url):
    """Yield a DB session with tables created and cleaned between tests."""
    async with create_db_session(
        database_url=worker_db_url, base=Base, cleanup=True, drop_tables=False
    ) as session:
        yield session


@pytest.fixture
def app_overrides(db_session: AsyncSession, mock_redis):
    """Point the app's db and redis dependencies at this test, for its whole run."""

    async def _db():
        yield db_session

    async def _redis():
        yield mock_redis

    app.dependency_overrides[db] = _db
    app.dependency_overrides[get_redis] = _redis
    try:
        yield
    finally:
        app.dependency_overrides.pop(db, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
def client_factory(app_overrides):
    """Returns a context manager that creates an isolated AsyncClient with test overrides."""

    @asynccontextmanager
    async def _create() -> AsyncIterator[AsyncClient]:
        async with create_async_client(
            app=app, base_url="http://127.0.0.1/api/v1"
        ) as c:
            yield c

    return _create


@pytest.fixture
async def http_client(client_factory) -> AsyncGenerator[AsyncClient]:
    """Unauthenticated test client."""
    async with client_factory() as c:
        yield c


@pytest.fixture
def override_db_context(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch get_db_context in security.py to reuse the test session.

    Functions like _verify_cookie() and create_api_token() call get_db_context()
    directly instead of using FastAPI dependency injection. Patching it in the
    security module namespace ensures they reuse the test session instead of
    opening a second connection on the same async task. Flushes on clean exit,
    as the real context commits.
    """
    from nexctf.api import security

    @asynccontextmanager
    async def _test_db_context() -> AsyncIterator[AsyncSession]:
        yield db_session
        await db_session.flush()

    monkeypatch.setattr(security, "get_db_context", _test_db_context)


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
) -> AsyncGenerator[tuple[AsyncClient, User]]:
    """Authenticated client logged in as an admin user."""
    async with _role_client(
        client_factory, db_session, "test_admin", "adminpass", UserRole.admin
    ) as item:
        yield item


@pytest.fixture
async def user_client(
    client_factory,
    db_session: AsyncSession,
    override_db_context,
) -> AsyncGenerator[tuple[AsyncClient, User]]:
    """Authenticated client logged in as a regular user."""
    async with _role_client(
        client_factory, db_session, "test_user", "userpass", UserRole.user
    ) as item:
        yield item


@pytest.fixture(params=["admin", "user"])
async def role_client(
    request,
    client_factory,
    db_session: AsyncSession,
    override_db_context,
) -> AsyncGenerator[tuple[AsyncClient, User]]:
    """Parametrized fixture that runs tests once per role (admin, user)."""
    role_map = {"admin": UserRole.admin, "user": UserRole.user}
    role = role_map[request.param]
    username = f"test_{request.param}"
    password = f"{request.param}pass"

    async with _role_client(
        client_factory, db_session, username, password, role
    ) as item:
        yield item
