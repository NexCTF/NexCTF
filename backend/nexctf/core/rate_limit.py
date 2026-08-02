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

import time
import uuid as _uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis

from nexctf.core import appconfig


async def check_rate_limit(
    redis: Redis,
    key: str,
    *,
    window_seconds: int,
    max_requests: int,
) -> None:
    """Sliding-window rate limit check. Raises HTTP 429 when the limit is exceeded.

    Uses a Redis sorted set where each member is a unique token and the score
    is the request timestamp (Unix seconds). Old entries outside the window are
    pruned on every call so the set never grows unboundedly.
    """
    now = time.time()
    member = f"{now:.6f}-{_uuid.uuid4().hex[:8]}"
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, "-inf", now - window_seconds)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds + 1)
    results = await pipe.execute()
    if results[2] > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before submitting again.",
        )


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
        window_seconds=int(
            appconfig.get_with_overrides(f"rate_limit.{name}.window_seconds", overrides)
        ),
        max_requests=int(
            appconfig.get_with_overrides(f"rate_limit.{name}.max_requests", overrides)
        ),
    )
