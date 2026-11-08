"""Unit tests for nexctf.module.info.version."""

import asyncio
from typing import Any

import pytest

from nexctf.module.info import version
from nexctf.module.info.version import CURRENT_VERSION, _is_newer, get_version_info
from nexctf.schema.info import VersionInfo

LATEST = VersionInfo(
    current=CURRENT_VERSION,
    latest="99.0.0",
    release_url="https://github.com/NexCTF/NexCTF/releases/tag/99.0.0",
    update_available=True,
)


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        ("0.4.0", "0.4.0", False),
        ("0.4.0", "0.5.0", True),
        ("0.4.0", "v0.5.0", True),
        ("0.4.0", "0.3.9", False),
        ("0.9.0", "0.10.0", True),
        ("0.4.0", "v1.0.0-hotfix", False),
        ("0.12.0.dev0", "0.12.0", False),
    ],
)
def test_update_available(current: str, latest: str, expected: bool) -> None:
    assert _is_newer(latest, current) is expected


class _FakeRedis:
    """Minimal dict-backed stand-in for the calls get_or_compute makes."""

    def __init__(self, initial: dict[str, bytes]) -> None:
        self.store = initial

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def mget(self, keys: list[str]) -> list[bytes | None]:
        return [self.store.get(k) for k in keys]

    async def set(self, key: str, value: str, *, nx: bool = False, **_: object) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value.encode()
        return True

    async def eval(self, _script: str, _numkeys: int, key: str, *args: Any) -> int:
        """Run the store script: write the value, the first argument after the keys."""
        if _numkeys > 1:
            self.store[key] = args[_numkeys - 1]
        else:
            self.store.pop(key, None)
        return 1


async def test_stale_cached_version_is_ignored_after_upgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blob cached by a previous release must not shadow the running version."""

    async def _fake_compute() -> VersionInfo:
        return VersionInfo(current=CURRENT_VERSION)

    monkeypatch.setattr(
        "nexctf.module.info.version._compute", _fake_compute, raising=True
    )
    stale = VersionInfo(
        current="0.0.1", latest=CURRENT_VERSION, update_available=True
    ).model_dump_json()
    redis: Any = _FakeRedis({"info:latest_release": stale.encode()})

    info = await get_version_info(redis)
    await _finish_refreshes()

    assert info.current == CURRENT_VERSION
    assert info.update_available is False


async def _finish_refreshes() -> None:
    await asyncio.gather(*version._refreshes)


class TestBackgroundRefresh:
    async def test_miss_answers_without_waiting_for_github(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        github = asyncio.Event()

        async def _slow_compute() -> VersionInfo:
            await github.wait()
            return LATEST

        monkeypatch.setattr(version, "_compute", _slow_compute)
        redis: Any = _FakeRedis({})

        assert await get_version_info(redis) == VersionInfo(current=CURRENT_VERSION)

        github.set()
        await _finish_refreshes()
        assert await get_version_info(redis) == LATEST

    async def test_hit_does_not_refresh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _unexpected() -> VersionInfo:
            raise AssertionError("cached value should be served")

        monkeypatch.setattr(version, "_compute", _unexpected)
        redis: Any = _FakeRedis({version._KEY: LATEST.model_dump_json().encode()})

        assert await get_version_info(redis) == LATEST
        assert not version._refreshes

    async def test_one_refresh_per_process(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = 0
        github = asyncio.Event()

        async def _counted() -> VersionInfo:
            nonlocal calls
            calls += 1
            await github.wait()
            return LATEST

        monkeypatch.setattr(version, "_compute", _counted)
        redis: Any = _FakeRedis({})

        await get_version_info(redis)
        await get_version_info(redis)
        github.set()
        await _finish_refreshes()

        assert calls == 1
