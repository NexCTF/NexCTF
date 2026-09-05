"""Tests for /admin/config bulk updates and their cache side effects."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import User
from nexctf.model.config import ConfigEntry


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


class TestSecretRedaction:
    """Secrets are masked on read and the mask is never written back."""

    @pytest.fixture
    def config_overrides(self) -> dict[str, str]:
        return {"email.smtp_password": "hunter2", "email.smtp_host": "smtp.test"}

    async def test_secret_masked_on_read(
        self,
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = admin_client
        resp = await c.get("/admin/config")
        items = {i["key"]: i["value"] for i in resp.json()["data"]}
        assert items["email.smtp_password"] == "***"
        assert items["email.smtp_host"] == "smtp.test"

    async def test_unset_secret_is_not_masked(
        self,
        admin_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """An empty secret reads back empty, so admins can tell it is unset."""
        del config_overrides["email.smtp_password"]
        c, _ = admin_client
        resp = await c.get("/admin/config")
        items = {i["key"]: i["value"] for i in resp.json()["data"]}
        assert items["email.smtp_password"] == ""

    async def test_mask_echoed_back_is_not_stored(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, _ = admin_client
        resp = await c.put(
            "/admin/config", json={"items": {"email.smtp_password": "***"}}
        )
        assert resp.status_code == 200
        stored = await db_session.execute(
            select(ConfigEntry).where(ConfigEntry.key == "email.smtp_password")
        )
        assert stored.scalar_one_or_none() is None
