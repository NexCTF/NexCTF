"""Worker-wide event bus: one Redis stream reader fanned out to in-process queues."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import defaultdict
from collections.abc import Iterator, Sequence
from typing import cast

from redis.asyncio import Redis

from nexctf.core.cache import get_client

logger = logging.getLogger(__name__)

_STREAM = "events"
_STREAM_MAXLEN = 10_000
_BLOCK_MS = 30_000
_RECONNECT_DELAY = 1
_QUEUE_MAXSIZE = 100

# Shape of an xread reply, which redis-py leaves untyped: one entry per stream
# read, each carrying (entry id, field mapping) pairs.
type _StreamRead = Sequence[tuple[str, Sequence[tuple[str, dict[str, str]]]]]

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_reader_task: asyncio.Task | None = None


async def publish_event(redis: Redis, channels: Sequence[str], data: str) -> None:
    """Append *data* to the stream once per channel, in a single round trip."""
    if not channels:
        return
    pipe = redis.pipeline(transaction=False)
    for channel in channels:
        pipe.xadd(
            _STREAM,
            {"channel": channel, "data": data},
            maxlen=_STREAM_MAXLEN,
            approximate=True,
        )
    await pipe.execute()


@contextlib.contextmanager
def subscription(channels: Sequence[str]) -> Iterator[asyncio.Queue[tuple[str, str]]]:
    """Hold a bounded queue registered for *channels* for the duration of the block."""
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    for channel in channels:
        _subscribers[channel].add(queue)
    _ensure_reader()
    try:
        yield queue
    finally:
        for channel in channels:
            _subscribers[channel].discard(queue)
            if not _subscribers[channel]:
                del _subscribers[channel]


def _dispatch(channel: str, data: str) -> None:
    """Hand one event to every queue registered for *channel*, dropping if full."""
    for queue in _subscribers.get(channel, ()):
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait((channel, data))


async def read_events(redis: Redis) -> None:
    """Fan the event stream out to the registered queues until cancelled."""
    last_id = "$"
    while True:
        try:
            streams = cast(
                _StreamRead,
                await redis.xread({_STREAM: last_id}, block=_BLOCK_MS) or (),
            )
            for _name, entries in streams:
                for last_id, fields in entries:
                    _dispatch(fields["channel"], fields["data"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("eventbus.reader_restart", exc_info=True)
            await asyncio.sleep(_RECONNECT_DELAY)


def _ensure_reader() -> None:
    """Start this worker's stream reader on the first subscriber."""
    global _reader_task
    if _reader_task is None or _reader_task.done():
        _reader_task = asyncio.create_task(read_events(get_client()))
