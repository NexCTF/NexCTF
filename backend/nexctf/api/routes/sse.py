import asyncio
import contextlib
from collections.abc import AsyncIterable, Callable

from fastapi import APIRouter, Security
from fastapi.sse import EventSourceResponse, ServerSentEvent

from nexctf.api.dep import RedisDep
from nexctf.api.security import auth
from nexctf.model import User, UserRole

sse_router = APIRouter(prefix="/stream", tags=["SSE"])


def _user_channels(user: User) -> list[str]:
    """Return all Redis pub/sub channels relevant to this user."""
    channels = ["notifications:broadcast"]
    if user.team_id is not None:
        channels.append(f"notifications:team:{user.team_id}")
    if user.role in (UserRole.admin, UserRole.moderator):
        channels.append("events:admin")
    return channels


async def _sse_listener(
    redis: RedisDep,
    channels: list[str],
    event_namer: "Callable[[str], str]",
) -> "AsyncIterable[ServerSentEvent]":
    """Generic SSE pump: subscribe to *channels*, yield typed ServerSentEvents."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(*channels)

    async def _reader(queue: asyncio.Queue):
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await queue.put((event_namer(msg["channel"]), msg["data"]))

    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    reader_task = asyncio.create_task(_reader(queue))
    try:
        while True:
            event_type, data = await queue.get()
            yield ServerSentEvent(raw_data=data, event=event_type)
    except asyncio.CancelledError:
        pass
    finally:
        reader_task.cancel()
        with contextlib.suppress(Exception):
            await reader_task
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(*channels)
        with contextlib.suppress(Exception):
            await pubsub.aclose()


@sse_router.get("", response_class=EventSourceResponse)
async def event_stream(
    redis: RedisDep,
    user: User = Security(auth),
) -> AsyncIterable[ServerSentEvent]:
    """Authenticated SSE stream.

    Event types emitted:
    - ``notification``     — new notification visible to this user
    - ``config_update``    — admin saved new config values
    """
    channels = [*_user_channels(user), "config:update"]

    def _name(channel: str) -> str:
        if channel == "config:update":
            return "config_update"
        if channel == "events:admin":
            return "event"
        return channel.split(":")[0].rstrip("s")

    async for event in _sse_listener(redis, channels, _name):
        yield event


@sse_router.get("/public", response_class=EventSourceResponse)
async def public_event_stream(
    redis: RedisDep,
) -> AsyncIterable[ServerSentEvent]:
    """Public (unauthenticated) SSE stream.

    Event types emitted:
    - ``config_update``  — admin saved new config values
    """
    async for event in _sse_listener(
        redis,
        ["config:update"],
        lambda _: "config_update",
    ):
        yield event
