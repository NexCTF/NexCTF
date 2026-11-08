"""Current app version + cached GitHub release check for the admin dashboard."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from importlib.metadata import version as pkg_version

import httpx
from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core.cache import get_cached, get_or_compute
from nexctf.schema.info import VersionInfo

logger = logging.getLogger(__name__)

CURRENT_VERSION = pkg_version("nexctf")

_REPO = "NexCTF/NexCTF"
_KEY = f"info:latest_release:{CURRENT_VERSION}"
_TTL = timedelta(hours=6)
_adapter: TypeAdapter[VersionInfo] = TypeAdapter(VersionInfo)
_refreshes: set[asyncio.Task[VersionInfo]] = set()


async def current_revision(session: AsyncSession) -> str | None:
    """Read the Alembic revision the live database is stamped with."""
    result = await session.execute(text("SELECT version_num FROM alembic_version"))
    return result.scalar_one_or_none()


def _parse(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.lstrip("v").split("."))


def _is_newer(latest: str, current: str) -> bool:
    """Whether release *latest* is newer than *current*; False if either is unparsable."""
    try:
        return _parse(latest) > _parse(current)
    except ValueError:
        return False


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
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("Could not check for a new NexCTF release: %r", exc)

    update_available = bool(latest and _is_newer(latest, CURRENT_VERSION))
    return VersionInfo(
        current=CURRENT_VERSION,
        latest=latest,
        release_url=release_url,
        update_available=update_available,
    )


def _refresh(redis: Redis, ttl: timedelta) -> None:
    """Check GitHub for the latest release in the background, once per process."""
    if _refreshes:
        return
    task = asyncio.create_task(get_or_compute(redis, _KEY, _adapter, _compute, ttl))
    _refreshes.add(task)
    task.add_done_callback(_refreshes.discard)


async def get_version_info(redis: Redis, ttl: timedelta = _TTL) -> VersionInfo:
    """Return the cached version info, checking GitHub in the background on a miss."""
    cached = await get_cached(redis, _KEY, _adapter)
    if cached is not None:
        return cached
    _refresh(redis, ttl)
    return VersionInfo(current=CURRENT_VERSION)
