import asyncio
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from nexctf.api.dep import CurrentUserDep
from nexctf.core import eventbus
from nexctf.core.config import settings
from nexctf.model import User, UserRole

sse_router = APIRouter(prefix="/stream", tags=["SSE"])

_active = {"authed": 0, "public": 0}


def _reject_if_full(budget: str, limit: int) -> None:
    """Raise 503 when *budget* is full. Read-only, so it cannot leak a slot."""
    if _active[budget] >= limit:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many open event streams. Please retry shortly.",
        )


async def _authed_capacity() -> None:
    _reject_if_full("authed", settings.SSE_MAX_STREAMS)


async def _public_capacity() -> None:
    _reject_if_full("public", settings.SSE_MAX_PUBLIC_STREAMS)


def _event_name(channel: str) -> str:
    """Map a bus channel to the SSE event type the frontend listens for."""
    if channel == "config:update":
        return "config_update"
    if channel == "events:admin":
        return "event"
    return channel.split(":")[0].rstrip("s")


def _user_channels(user: User) -> list[str]:
    """Return all event channels relevant to this user."""
    channels = ["notifications:broadcast"]
    if user.team_id is not None:
        channels.append(f"notifications:team:{user.team_id}")
    if user.role in (UserRole.admin, UserRole.moderator):
        channels.append("events:admin")
    return channels


async def _sse_listener(
    channels: list[str], budget: str
) -> AsyncIterable[ServerSentEvent]:
    """Yield the bus events for *channels* as typed ServerSentEvents."""
    with eventbus.subscription(channels) as queue:
        _active[budget] += 1
        try:
            while True:
                channel, data = await queue.get()
                yield ServerSentEvent(raw_data=data, event=_event_name(channel))
        except asyncio.CancelledError:
            pass
        finally:
            _active[budget] -= 1


@sse_router.get(
    "",
    response_class=EventSourceResponse,
    dependencies=[Depends(_authed_capacity)],
)
async def event_stream(user: CurrentUserDep) -> AsyncIterable[ServerSentEvent]:
    """Authenticated SSE stream.

    Event types emitted:
    - ``notification``     — new notification visible to this user
    - ``config_update``    — admin saved new config values
    - ``event``            — admin/moderator audit event
    """
    channels = [*_user_channels(user), "config:update"]
    async for event in _sse_listener(channels, "authed"):
        yield event


@sse_router.get(
    "/public",
    response_class=EventSourceResponse,
    dependencies=[Depends(_public_capacity)],
)
async def public_event_stream() -> AsyncIterable[ServerSentEvent]:
    """Public (unauthenticated) SSE stream.

    Event types emitted:
    - ``config_update``  — admin saved new config values
    """
    async for event in _sse_listener(["config:update"], "public"):
        yield event
