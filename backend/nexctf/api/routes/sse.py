import asyncio
import logging
from collections import Counter
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from nexctf.api.dep import CurrentUserDep, TokenScopesDep
from nexctf.api.scope import ADMIN_EVENTS_SCOPE
from nexctf.core import eventbus
from nexctf.core.config import settings
from nexctf.model import User, UserRole
from nexctf.util.ip import get_client_ip

logger = logging.getLogger(__name__)

sse_router = APIRouter(prefix="/stream", tags=["SSE"])

_active = {"authed": 0, "public": 0}
_by_owner: Counter[str] = Counter()


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


def _reject_if_owner_full(owner: str, limit: int) -> None:
    """Raise 429 when *owner* already holds *limit* streams on this worker."""
    if _by_owner[owner] >= limit:
        logger.warning(
            "sse stream rejected, %s holds too many",
            owner,
            extra={"owner": owner, "limit": limit},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many open event streams. Close a tab and retry.",
        )


def _user_owner(user: User) -> str:
    return f"user:{user.id}"


def _ip_owner(request: Request) -> str:
    return f"ip:{get_client_ip(request) or 'unknown'}"


async def _authed_capacity() -> None:
    _reject_if_full("authed", settings.SSE_MAX_STREAMS)


async def _public_capacity() -> None:
    _reject_if_full("public", settings.SSE_MAX_PUBLIC_STREAMS)


async def _user_capacity(user: CurrentUserDep) -> None:
    _reject_if_owner_full(_user_owner(user), settings.SSE_MAX_STREAMS_PER_USER)


async def _ip_capacity(request: Request) -> None:
    _reject_if_owner_full(_ip_owner(request), settings.SSE_MAX_PUBLIC_STREAMS_PER_IP)


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


async def _sse_listener(
    channels: list[str],
    budget: str,
    owner: str,
    close_on: str | None = None,
) -> AsyncIterable[ServerSentEvent]:
    """Yield the bus events for *channels* as typed ServerSentEvents.

    *close_on* is subscribed too, and an event on it ends the stream. The
    stream counts against *owner*'s share while it is open.
    """
    subscribed = [*channels, close_on] if close_on else channels
    with eventbus.subscription(subscribed) as queue:
        _active[budget] += 1
        _by_owner[owner] += 1
        logger.debug(
            "sse stream opened",
            extra={"budget": budget, "active": _active[budget]},
        )
        try:
            while True:
                channel, data = await queue.get()
                if channel == close_on:
                    return
                yield ServerSentEvent(raw_data=data, event=_event_name(channel))
        except asyncio.CancelledError:
            pass
        finally:
            _active[budget] -= 1
            _by_owner[owner] -= 1
            if _by_owner[owner] <= 0:
                del _by_owner[owner]
            logger.debug(
                "sse stream closed",
                extra={"budget": budget, "active": _active[budget]},
            )


@sse_router.get(
    "",
    response_class=EventSourceResponse,
    dependencies=[Depends(_authed_capacity), Depends(_user_capacity)],
)
async def event_stream(
    user: CurrentUserDep, granted: TokenScopesDep
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
        channels, "authed", _user_owner(user), close_on=close_on
    ):
        yield event


@sse_router.get(
    "/public",
    response_class=EventSourceResponse,
    dependencies=[Depends(_public_capacity), Depends(_ip_capacity)],
)
async def public_event_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    """Public (unauthenticated) SSE stream.

    Event types emitted:
    - ``config_update``  — admin saved new config values
    """
    async for event in _sse_listener(["config:update"], "public", _ip_owner(request)):
        yield event
