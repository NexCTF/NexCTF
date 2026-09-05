"""Tests for the worker event bus (nexctf.core.eventbus)."""

import asyncio

import pytest

from nexctf.core import eventbus


@pytest.fixture
async def reader_client():
    """The module's reader client, closed and reset after the test."""
    client = eventbus.get_reader_client()
    try:
        await client.ping()
    except OSError:
        pytest.skip("Redis not reachable")
    yield client
    await client.aclose()
    eventbus._reader_client = None


def test_read_timeout_outlives_the_xread_block(reader_client):
    """A socket timeout under the block would abort every idle read."""
    timeout = reader_client.connection_pool.connection_kwargs["socket_timeout"]

    assert timeout > eventbus._BLOCK_MS / 1000


async def test_published_event_reaches_a_subscriber(reader_client):
    """An event published on a subscribed channel lands in that channel's queue."""
    with eventbus.subscription(["test:eventbus"]) as queue:
        await asyncio.sleep(0.1)
        await eventbus.publish_event(reader_client, ["test:eventbus"], "payload")

        assert await asyncio.wait_for(queue.get(), timeout=5) == (
            "test:eventbus",
            "payload",
        )

    if eventbus._reader_task:
        eventbus._reader_task.cancel()
        eventbus._reader_task = None
