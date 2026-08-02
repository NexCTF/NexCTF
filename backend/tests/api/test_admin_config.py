"""Tests for /admin/config bulk updates and their cache side effects."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from nexctf.model import User


def _patch_invalidate():
    return patch(
        "nexctf.api.routes.admin.config.invalidate_scoreboard", new_callable=AsyncMock
    )


class TestFreezeTimeInvalidation:
    """A freeze-time change drops the cached scoreboard blobs."""

    async def test_freeze_time_change_drops_scoreboard_caches(
        self,
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = admin_client
        with _patch_invalidate() as invalidate:
            resp = await c.put(
                "/admin/config",
                json={"items": {"ctf.freeze_time": "2099-01-01T00:00:00+00:00"}},
            )
        assert resp.status_code == 200
        invalidate.assert_awaited_once()

    async def test_unrelated_key_leaves_scoreboard_caches_alone(
        self,
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = admin_client
        with _patch_invalidate() as invalidate:
            resp = await c.put("/admin/config", json={"items": {"ctf.name": "NexCTF"}})
        assert resp.status_code == 200
        invalidate.assert_not_awaited()
