from __future__ import annotations

import inspect
from typing import Any, Callable


async def call_maybe_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call fn(*args, **kwargs), awaiting the result if it is a coroutine."""
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result
