"""Shared fixtures for tests/module integration tests."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def sessions(worker_db_url: str) -> AsyncIterator[async_sessionmaker]:
    """A session factory on its own engine, for concurrent transactions."""
    engine = create_async_engine(worker_db_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
