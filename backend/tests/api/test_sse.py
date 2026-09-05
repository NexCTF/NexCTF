"""Tests for the SSE stream connection caps and the worker-wide event bus."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterable
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.sse import ServerSentEvent
from httpx import AsyncClient
from redis.asyncio import Redis

from nexctf.api.routes import sse
from nexctf.core import eventbus
from nexctf.core.config import settings
from nexctf.model import User


@pytest.fixture(autouse=True)
def reset_state():
    sse._active.update(authed=0, public=0)
    eventbus._subscribers.clear()
    eventbus._reader_task = None
    yield
    if eventbus._reader_task is not None:
        eventbus._reader_task.cancel()


def _open(channels: list[str], budget: str = "public") -> asyncio.Task:
    """Start a listener and drain it in the background."""

    async def _drain(stream: AsyncIterable[ServerSentEvent]) -> None:
        async for _ in stream:
            pass

    return asyncio.create_task(_drain(sse._sse_listener(channels, budget)))


class TestStreamCapacity:
    async def test_public_stream_rejected_when_full(
        self, http_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A full public budget answers 503 instead of opening another stream."""
        monkeypatch.setattr(settings, "SSE_MAX_PUBLIC_STREAMS", 1)
        sse._active["public"] = 1
        resp = await http_client.get("/stream/public")
        assert resp.status_code == 503

    async def test_authed_stream_rejected_when_full(
        self, user_client: tuple[AsyncClient, User], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The authenticated budget is separate and capped the same way."""
        monkeypatch.setattr(settings, "SSE_MAX_STREAMS", 1)
        sse._active["authed"] = 1
        c, _ = user_client
        resp = await c.get("/stream")
        assert resp.status_code == 503

    async def test_budgets_are_independent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A saturated public budget must not reject authenticated streams."""
        monkeypatch.setattr(settings, "SSE_MAX_PUBLIC_STREAMS", 1)
        monkeypatch.setattr(settings, "SSE_MAX_STREAMS", 10)
        sse._active["public"] = 50

        await sse._authed_capacity()
        with pytest.raises(HTTPException):
            await sse._public_capacity()

    async def test_slot_and_registration_released_when_stream_ends(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A leaked registration is a phantom subscriber the reader keeps feeding."""
        monkeypatch.setattr(eventbus, "_ensure_reader", lambda: None)
        task = _open(["config:update", "events:admin"])
        await asyncio.sleep(0.05)
        assert sse._active["public"] == 1
        assert len(eventbus._subscribers["config:update"]) == 1

        task.cancel()
        with contextlib.suppress(BaseException):
            await task
        assert sse._active["public"] == 0
        assert not eventbus._subscribers


class TestEventBus:
    async def test_one_reader_serves_every_stream(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The worker opens a single stream reader no matter how many clients connect."""
        started = 0

        async def _fake_reader(_redis) -> None:
            nonlocal started
            started += 1
            await asyncio.Event().wait()

        monkeypatch.setattr(eventbus, "read_events", _fake_reader)
        monkeypatch.setattr(eventbus, "get_reader_client", lambda: None)
        streams = [_open(["config:update"]) for _ in range(5)]
        await asyncio.sleep(0.05)

        assert started == 1
        assert sse._active["public"] == 5

        for task in streams:
            task.cancel()

    async def test_events_reach_only_their_own_channel(self) -> None:
        """Routing is exact-match, so a team channel never leaks to another team."""
        with (
            eventbus.subscription(["notifications:team:a"]) as mine,
            eventbus.subscription(["notifications:team:b"]) as theirs,
        ):
            eventbus._dispatch("notifications:team:a", "secret")

            assert mine.get_nowait() == ("notifications:team:a", "secret")
            assert theirs.empty()

    async def test_a_full_queue_does_not_stall_the_reader(self) -> None:
        """One client too slow to drain must not block delivery to the others."""
        slow: asyncio.Queue = asyncio.Queue(maxsize=2)
        fast: asyncio.Queue = asyncio.Queue(maxsize=2)
        eventbus._subscribers["config:update"].add(slow)
        eventbus._subscribers["events:admin"].add(fast)
        batch = [_entry(str(i), "config:update", "1") for i in range(50)]
        batch.append(_entry("50", "events:admin", "later"))

        task = asyncio.create_task(
            eventbus.read_events(cast(Redis, _FakeRedis([batch])))
        )
        await asyncio.sleep(0.05)

        assert slow.qsize() == 2
        assert fast.qsize() == 1
        task.cancel()

    async def test_reader_resumes_from_the_last_event_it_saw(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A Redis blip must cost no events: the reader picks up where it stopped."""
        monkeypatch.setattr(eventbus, "_RECONNECT_DELAY", 0)
        queue: asyncio.Queue = asyncio.Queue(maxsize=5)
        eventbus._subscribers["config:update"].add(queue)
        redis = _FakeRedis(
            [
                [_entry("5-0", "config:update", "before")],
                [_entry("6-0", "config:update", "after")],
            ],
            fail_on_read=2,
        )

        task = asyncio.create_task(eventbus.read_events(cast(Redis, redis)))
        await asyncio.sleep(0.05)

        # Read 1 delivered 5-0, read 2 failed; read 3 must resume from 5-0, not "$".
        assert redis.requested_ids[:3] == ["$", "5-0", "5-0"]
        assert queue.get_nowait() == ("config:update", "before")
        assert queue.get_nowait() == ("config:update", "after")
        task.cancel()

    async def test_publish_sends_one_entry_per_channel(self) -> None:
        """Fanning out to N channels costs one round trip, not N."""
        redis = _FakePipelineRedis()
        await eventbus.publish_event(
            cast(Redis, redis), ["notifications:team:a", "notifications:team:b"], "hi"
        )

        assert redis.executes == 1
        assert [c["channel"] for c in redis.added] == [
            "notifications:team:a",
            "notifications:team:b",
        ]


def _entry(entry_id: str, channel: str, data: str) -> tuple[str, dict[str, str]]:
    return entry_id, {"channel": channel, "data": data}


class _FakeRedis:
    """Replays scripted xread batches, then holds the read open like a real one."""

    def __init__(
        self,
        batches: list[list[tuple[str, dict[str, str]]]],
        fail_on_read: int | None = None,
    ) -> None:
        self._batches = list(batches)
        self._fail_on_read = fail_on_read
        self.requested_ids: list[str] = []

    async def xread(self, streams: dict[str, str], block: int | None = None):
        self.requested_ids.append(next(iter(streams.values())))
        if len(self.requested_ids) == self._fail_on_read:
            raise ConnectionError("boom")
        if self._batches:
            return [["events", self._batches.pop(0)]]
        await asyncio.Event().wait()


class _FakePipelineRedis:
    """Records the xadds queued on a pipeline and how often it was executed."""

    def __init__(self) -> None:
        self.added: list[dict[str, str]] = []
        self.executes = 0

    def pipeline(self, transaction: bool = True) -> _FakePipelineRedis:
        return self

    def xadd(self, stream: str, fields: dict[str, str], **kwargs) -> None:
        self.added.append(fields)

    async def execute(self) -> None:
        self.executes += 1
