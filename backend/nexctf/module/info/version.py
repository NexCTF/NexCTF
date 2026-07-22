"""Current app version + cached GitHub release check for the admin dashboard."""

from __future__ import annotations

import logging
from datetime import timedelta
from importlib.metadata import version as pkg_version

import httpx
from pydantic import TypeAdapter
from redis.asyncio import Redis

from nexctf.core.cache import get_or_compute
from nexctf.schema.info import VersionInfo

logger = logging.getLogger(__name__)

CURRENT_VERSION = pkg_version("nexctf")

_REPO = "NexCTF/NexCTF"
_KEY = "info:latest_release"
_TTL = timedelta(hours=6)
_adapter: TypeAdapter[VersionInfo] = TypeAdapter(VersionInfo)


def _parse(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.lstrip("v").split("."))


async def _compute() -> VersionInfo:
    latest: str | None = None
    release_url: str | None = None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{_REPO}/releases/latest"
            )
        if resp.status_code == 200:
            data = resp.json()
            latest = data["tag_name"]
            release_url = data["html_url"]
    except (httpx.HTTPError, KeyError, ValueError):
        # ponytail: GitHub unreachable or no release published yet -> skip the
        # check for this TTL window, retry on next cache expiry.
        logger.warning("Could not check for a new NexCTF release", exc_info=True)

    update_available = bool(latest and _parse(latest) > _parse(CURRENT_VERSION))
    return VersionInfo(
        current=CURRENT_VERSION,
        latest=latest,
        release_url=release_url,
        update_available=update_available,
    )


async def get_version_info(redis: Redis, ttl: timedelta = _TTL) -> VersionInfo:
    """Return the cached current/latest version info for the admin dashboard."""
    return await get_or_compute(redis, _KEY, _adapter, _compute, ttl)
