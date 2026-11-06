"""Sliding-window rate limiter backed by Redis sorted sets.

Usage in a route — ``overrides`` is the per-request config snapshot from
``nexctf.api.dep.ConfigDep``::

    from nexctf.core.rate_limit import check_config_rate_limit

    await check_config_rate_limit(
        redis, overrides, name="submit", key=f"rl:submit:{user.id}"
    )

Plugins can import and call ``check_rate_limit`` directly with any key.
"""

from __future__ import annotations

import logging
import time
import uuid as _uuid

from fastapi import Request
from redis.asyncio import Redis

from nexctf.core import appconfig
from nexctf.core.metrics import incr_counter
from nexctf.exceptions import RateLimitedError
from nexctf.util.ip import get_client_ip

logger = logging.getLogger(__name__)


def client_rate_key(action: str, request: Request) -> str:
    """Redis key limiting *action* per client address."""
    return f"rl:{action}:{get_client_ip(request) or 'unknown'}"


def _member(now: float) -> str:
    """A unique sorted-set member for one request at *now*."""
    return f"{now:.6f}-{_uuid.uuid4().hex[:8]}"


async def _refuse(redis: Redis, key: str, limit: int, name: str) -> None:
    """Log and count a refusal, then raise RateLimitedError."""
    logger.warning(
        "rate limit hit on %s", key, extra={"limit_key": key, "max_requests": limit}
    )
    await incr_counter(redis, "rate_limited", name)
    raise RateLimitedError()


async def check_rate_limit(
    redis: Redis,
    key: str,
    *,
    window_seconds: int,
    max_requests: int,
    name: str = "other",
) -> None:
    """Sliding-window rate limit check. Raises RateLimitedError when the limit is exceeded.

    Uses a Redis sorted set where each member is a unique token and the score
    is the request timestamp (Unix seconds). Old entries outside the window are
    pruned on every call so the set never grows unboundedly. A refused request
    is not counted, so the window frees up while a client keeps retrying.
    """
    now = time.time()
    member = _member(now)
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, "-inf", now - window_seconds)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds + 1)
    results = await pipe.execute()
    if results[2] > max_requests:
        await redis.zrem(key, member)
        await _refuse(redis, key, max_requests, name)


async def failure_limit_reached(
    redis: Redis, key: str, *, window_seconds: int, max_failures: int
) -> bool:
    """Whether *key* recorded *max_failures* within the window."""
    since = time.time() - window_seconds
    return await redis.zcount(key, f"({since}", "+inf") >= max_failures


async def check_failure_limit(
    redis: Redis, key: str, *, window_seconds: int, max_failures: int, name: str
) -> None:
    """Raise RateLimitedError once *key* recorded *max_failures* within the window."""
    if await failure_limit_reached(
        redis, key, window_seconds=window_seconds, max_failures=max_failures
    ):
        await _refuse(redis, key, max_failures, name)


async def record_failure(redis: Redis, key: str, *, window_seconds: int) -> None:
    """Count one failure against *key* for ``check_failure_limit``."""
    now = time.time()
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, "-inf", now - window_seconds)
    pipe.zadd(key, {_member(now): now})
    pipe.expire(key, window_seconds + 1)
    await pipe.execute()


async def check_config_rate_limit(
    redis: Redis,
    overrides: dict[str, str],
    *,
    name: str,
    key: str,
) -> None:
    """Apply the ``rate_limit.<name>.*`` config group, no-op when it is disabled.

    Args:
        redis: Redis client backing the sliding window.
        overrides: Per-request config snapshot shared across workers.
        name: Config group name, e.g. ``"submit"`` or ``"login"``.
        key: Redis key identifying the caller being limited.
    """
    if not appconfig.get_with_overrides(f"rate_limit.{name}.enabled", overrides):
        return
    await check_rate_limit(
        redis,
        key,
        name=name,
        window_seconds=int(
            appconfig.get_with_overrides(f"rate_limit.{name}.window_seconds", overrides)
        ),
        max_requests=int(
            appconfig.get_with_overrides(f"rate_limit.{name}.max_requests", overrides)
        ),
    )
