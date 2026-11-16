"""Open event-stream slots, counted in Redis so every worker sees the same totals.

A stream holds one slot in the share it counts against, for example its user
or its client address. A slot expires unless its stream keeps refreshing it,
so a worker that dies does not leave its streams counted forever.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, cast

from redis.asyncio import Redis

SLOT_TTL_SECONDS = 90
REFRESH_SECONDS = 30

_KEY_PREFIX = "sse:slots:"

# KEYS: the share's sorted set. ARGV: now, expiry, ttl, member, limit.
# Returns 1 when a slot was taken, 0 when the share is full.
_ACQUIRE = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[5]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return 1
"""


@dataclass(frozen=True)
class Share:
    """A named pool of slots and how many streams it admits."""

    name: str
    limit: int

    @property
    def key(self) -> str:
        """Redis key of this share's sorted set."""
        return f"{_KEY_PREFIX}{self.name}"


@dataclass(frozen=True)
class Slot:
    """One stream's hold on a slot in its share."""

    member: str
    key: str


class ShareFullError(Exception):
    """Raised when a share has no free slot."""

    def __init__(self, share: Share) -> None:
        super().__init__(share.name)
        self.share = share


def new_slot(share: Share) -> Slot:
    """A slot in *share* that is not taken yet; refresh() takes it."""
    return Slot(member=uuid.uuid4().hex, key=share.key)


async def acquire(redis: Redis, share: Share, *, now: float | None = None) -> Slot:
    """Take a slot in *share*, or raise ShareFullError."""
    now = time.time() if now is None else now
    slot = new_slot(share)
    script = redis.register_script(_ACQUIRE)
    args = [now, now + SLOT_TTL_SECONDS, SLOT_TTL_SECONDS, slot.member, share.limit]
    if not await cast(Any, script(keys=[slot.key], args=args)):
        raise ShareFullError(share)
    return slot


async def refresh(redis: Redis, slot: Slot, *, now: float | None = None) -> None:
    """Push back the expiry of *slot*, taking it again if it had lapsed."""
    now = time.time() if now is None else now
    pipe = redis.pipeline()
    pipe.zadd(slot.key, {slot.member: now + SLOT_TTL_SECONDS})
    pipe.expire(slot.key, SLOT_TTL_SECONDS)
    await pipe.execute()


async def release(redis: Redis, slot: Slot) -> None:
    """Give *slot* back in its share."""
    await redis.zrem(slot.key, slot.member)
