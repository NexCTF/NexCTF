import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from redis.asyncio import Redis
from redis.exceptions import RedisError

from nexctf.api.dep import CurrentUserDep, RedisDep, TokenScopesDep
from nexctf.api.scope import ADMIN_EVENTS_SCOPE
from nexctf.core import eventbus, stream_slots
from nexctf.core.config import settings
from nexctf.core.stream_slots import Share, Slot
from nexctf.model import User, UserRole
from nexctf.util.ip import client_address

logger = logging.getLogger(__name__)

sse_router = APIRouter(prefix="/stream", tags=["SSE"])

# Streams open on this worker, per budget
_active = {"authed": 0, "public": 0}


def _reject_if_full(budget: str, limit: int) -> None:
    """Raise 503 when *budget* is full. Read-only, so it cannot leak a slot."""
    if _active[budget] >= limit:
        logger.warning(
            "sse stream rejected, %s budget full",
            budget,
            extra={"budget": budget, "limit": limit},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many open event streams. Please retry shortly.",
        )


async def _take_slot(redis: Redis, share: Share) -> Slot:
    """Take a slot in *share*, or raise 429 when it is full.

    Without Redis the stream is let in uncounted; its first refresh counts it.
    """
    try:
        return await stream_slots.acquire(redis, share)
    except RedisError:
        logger.warning("sse slot not counted, redis unavailable", exc_info=True)
        return stream_slots.new_slot(share)
    except stream_slots.ShareFullError as exc:
        logger.warning(
            "sse stream rejected, %s holds too many",
            exc.share.name,
            extra={"owner": exc.share.name, "limit": exc.share.limit},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many open event streams. Close a tab and retry.",
        )


async def _authed_capacity() -> None:
    _reject_if_full("authed", settings.SSE_MAX_STREAMS)


async def _public_capacity() -> None:
    _reject_if_full("public", settings.SSE_MAX_PUBLIC_STREAMS)


@contextlib.asynccontextmanager
async def _hold_slot(redis: Redis, share: Share) -> AsyncGenerator[Slot]:
    """Hold a slot in *share* until the response is over, however it ends."""
    slot = await _take_slot(redis, share)
    try:
        yield slot
    finally:
        _release_soon(redis, slot)


async def _user_slot(redis: RedisDep, user: CurrentUserDep) -> AsyncGenerator[Slot]:
    """A slot counted against the caller's account."""
    share = Share(f"user:{user.id}", settings.SSE_MAX_STREAMS_PER_USER)
    async with _hold_slot(redis, share) as slot:
        yield slot


async def _public_slot(request: Request, redis: RedisDep) -> AsyncGenerator[Slot]:
    """A slot counted against the caller's address."""
    share = Share(
        f"public:ip:{client_address(request)}",
        settings.SSE_MAX_PUBLIC_STREAMS_PER_IP,
    )
    async with _hold_slot(redis, share) as slot:
        yield slot


UserSlotDep = Annotated[Slot, Depends(_user_slot)]
PublicSlotDep = Annotated[Slot, Depends(_public_slot)]


def _event_name(channel: str) -> str:
    """Map a bus channel to the SSE event type the frontend listens for."""
    if channel == "config:update":
        return "config_update"
    if channel == "events:admin":
        return "event"
    return channel.split(":")[0].rstrip("s")


def _may_read_admin_events(granted: frozenset[str] | None) -> bool:
    """Whether a caller holding *granted* may receive the admin audit channel."""
    return granted is None or ADMIN_EVENTS_SCOPE in granted


def _user_channels(user: User, granted: frozenset[str] | None) -> list[str]:
    """Return all event channels relevant to this user."""
    channels = ["notifications:broadcast"]
    if user.team_id is not None:
        channels.append(f"notifications:team:{user.team_id}")
    if user.role is UserRole.admin and _may_read_admin_events(granted):
        channels.append("events:admin")
    return channels


_releases: set[asyncio.Task[None]] = set()


async def _release(redis: Redis, slot: Slot) -> None:
    with contextlib.suppress(RedisError):
        await stream_slots.release(redis, slot)


def _release_soon(redis: Redis, slot: Slot) -> None:
    """Give *slot* back from a task of its own, out of reach of a cancellation."""
    task = asyncio.create_task(_release(redis, slot))
    _releases.add(task)
    task.add_done_callback(_releases.discard)


async def _keep_slot(redis: Redis, slot: Slot, due: float) -> float:
    """Refresh *slot* once *due* has passed, returning when it is next due."""
    now = time.monotonic()
    if now < due:
        return due
    with contextlib.suppress(RedisError):
        await stream_slots.refresh(redis, slot)
    return now + stream_slots.REFRESH_SECONDS


async def _sse_listener(
    channels: list[str],
    budget: str,
    redis: Redis,
    slot: Slot,
    close_on: str | None = None,
) -> AsyncIterable[ServerSentEvent]:
    """Yield the bus events for *channels* as typed ServerSentEvents.

    *close_on* is subscribed too, and an event on it ends the stream. The
    stream keeps *slot* alive while it is open; its dependency gives it back.
    """
    subscribed = [*channels, close_on] if close_on else channels
    with eventbus.subscription(subscribed) as queue:
        _active[budget] += 1
        logger.debug(
            "sse stream opened",
            extra={"budget": budget, "active": _active[budget]},
        )
        due = time.monotonic() + stream_slots.REFRESH_SECONDS
        try:
            while True:
                due = await _keep_slot(redis, slot, due)
                try:
                    channel, data = await asyncio.wait_for(
                        queue.get(), timeout=max(due - time.monotonic(), 0)
                    )
                except TimeoutError:
                    continue
                if channel == close_on:
                    return
                yield ServerSentEvent(raw_data=data, event=_event_name(channel))
        except asyncio.CancelledError:
            pass
        finally:
            _active[budget] -= 1
            logger.debug(
                "sse stream closed",
                extra={"budget": budget, "active": _active[budget]},
            )


@sse_router.get(
    "",
    response_class=EventSourceResponse,
    dependencies=[Depends(_authed_capacity)],
)
async def event_stream(
    redis: RedisDep, user: CurrentUserDep, granted: TokenScopesDep, slot: UserSlotDep
) -> AsyncIterable[ServerSentEvent]:
    """Authenticated SSE stream.

    Event types emitted:
    - ``notification``     — new notification visible to this user
    - ``config_update``    — admin saved new config values
    - ``event``            — admin audit event
    """
    channels = [*_user_channels(user, granted), "config:update"]
    close_on = eventbus.user_stream_channel(user.id)
    async for event in _sse_listener(
        channels, "authed", redis, slot, close_on=close_on
    ):
        yield event


@sse_router.get(
    "/public",
    response_class=EventSourceResponse,
    dependencies=[Depends(_public_capacity)],
)
async def public_event_stream(
    redis: RedisDep, slot: PublicSlotDep
) -> AsyncIterable[ServerSentEvent]:
    """Public (unauthenticated) SSE stream.

    Event types emitted:
    - ``config_update``  — admin saved new config values
    """
    async for event in _sse_listener(["config:update"], "public", redis, slot):
        yield event
