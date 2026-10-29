"""Shared fixtures for tests/core integration tests."""

import uuid

import pytest


@pytest.fixture
async def cache_key(redis):
    """Unique Redis key that is deleted from the server after each test."""
    key = f"test:cache:{uuid.uuid4()}"
    yield key
    await redis.delete(key)


@pytest.fixture
def s3_key() -> str:
    """Unique S3 object key per test."""
    return f"test/{uuid.uuid4()}"
