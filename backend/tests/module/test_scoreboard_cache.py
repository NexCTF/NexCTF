"""Tests for which scoreboard caches a play drops."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from nexctf.module.scoreboard import cache
from nexctf.module.scoreboard.cache import invalidate_play

FREEZE = datetime(2026, 1, 1, 12, tzinfo=UTC)
FROZEN = {"ctf.freeze_time": FREEZE.isoformat()}


@pytest.fixture
def dropped(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every registry and key the cache drops."""
    names: list[str] = []

    async def _record(_redis: object, *dropped_names: str) -> None:
        names.extend(dropped_names)

    monkeypatch.setattr(cache, "drop_registered", _record)
    monkeypatch.setattr(cache, "drop_keys", _record)
    return names


async def test_a_play_after_the_freeze_only_drops_the_admin_board(
    dropped: list[str],
) -> None:
    await invalidate_play(
        AsyncMock(), uuid4(), played_at=FREEZE + timedelta(seconds=1), overrides=FROZEN
    )

    assert dropped == [cache._ADMIN_REGISTRY]


async def test_a_play_before_the_freeze_drops_every_board(
    dropped: list[str],
) -> None:
    team_id = uuid4()

    await invalidate_play(
        AsyncMock(), team_id, played_at=FREEZE - timedelta(seconds=1), overrides=FROZEN
    )

    assert set(dropped) == {
        cache._BOARD_REGISTRY,
        cache._ADMIN_REGISTRY,
        f"scoreboard:team:{team_id}",
    }


async def test_without_a_freeze_a_play_drops_every_board(
    dropped: list[str],
) -> None:
    await invalidate_play(AsyncMock(), uuid4(), played_at=FREEZE, overrides={})

    assert {cache._BOARD_REGISTRY, cache._ADMIN_REGISTRY} <= set(dropped)


async def test_the_admin_board_has_its_own_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registries: list[str | None] = []

    async def _get_or_compute(*_args: object, registry: str | None = None) -> None:
        registries.append(registry)

    monkeypatch.setattr(cache, "get_or_compute", _get_or_compute)
    await cache.get_admin_scoreboard(AsyncMock(), AsyncMock(), overrides={})
    await cache.get_scoreboard(AsyncMock(), AsyncMock(), overrides={})

    assert registries == [cache._ADMIN_REGISTRY, cache._BOARD_REGISTRY]
