"""Unit tests for nexctf.module.info.version semver comparison."""

from typing import Any

import pytest

from nexctf.module.info.version import CURRENT_VERSION, _parse, get_version_info
from nexctf.schema.info import VersionInfo


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        ("0.4.0", "0.4.0", False),
        ("0.4.0", "0.5.0", True),
        ("0.4.0", "v0.5.0", True),
        ("0.4.0", "0.3.9", False),
        ("0.9.0", "0.10.0", True),
    ],
)
def test_update_available(current: str, latest: str, expected: bool) -> None:
    assert (_parse(latest) > _parse(current)) is expected


class _FakePipeline:
    """Applies the queued writes on execute, like a redis pipeline."""

    def __init__(self, store: dict[str, bytes]) -> None:
        self.store = store

    def setex(self, key: str, _ttl: int, value: bytes) -> None:
        self.store[key] = value

    def sadd(self, _registry: str, _key: str) -> None:
        pass

    async def execute(self) -> list[None]:
        return []


class _FakeRedis:
    """Minimal dict-backed stand-in for the calls get_or_compute makes."""

    def __init__(self, initial: dict[str, bytes]) -> None:
        self.store = initial

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self.store)


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

    assert info.current == CURRENT_VERSION
    assert info.update_available is False
