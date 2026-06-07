"""Unit tests for nexctf.util.async_utils.call_maybe_async."""

from nexctf.util.async_utils import call_maybe_async


async def test_awaits_coroutine():
    async def afn(x: int) -> int:
        return x * 2

    assert await call_maybe_async(afn, 3) == 6


async def test_calls_sync_function():
    def sfn(x: int) -> int:
        return x + 1

    assert await call_maybe_async(sfn, 10) == 11


async def test_forwards_kwargs():
    async def afn(a: int, b: int = 0) -> int:
        return a + b

    assert await call_maybe_async(afn, 1, b=4) == 5


async def test_sync_with_kwargs():
    def sfn(a: int, b: int = 0) -> int:
        return a * b

    assert await call_maybe_async(sfn, 3, b=3) == 9
