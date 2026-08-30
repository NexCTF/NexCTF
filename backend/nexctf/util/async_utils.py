from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi_toolsets.db import transaction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def call_maybe_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call fn(*args, **kwargs), awaiting the result if it is a coroutine."""
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def dispatch_hook(session: AsyncSession, hook: Awaitable[None]) -> None:
    """Await a lifecycle hook in a savepoint, logging and swallowing any failure."""
    try:
        async with transaction(session):
            await hook
    except Exception:
        logger.exception("hook failed")
