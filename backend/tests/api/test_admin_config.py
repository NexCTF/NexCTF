"""Tests for /admin/config bulk updates and their cache side effects."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import User
from nexctf.model.config import ConfigEntry


def _patch_invalidate():
    return patch("nexctf.module.config.invalidate_scoreboard", new_callable=AsyncMock)


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


class TestBounds:
    """Numeric bounds are published and enforced on save."""

    async def test_bounds_in_listing(
        self,
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = admin_client
        resp = await c.get("/admin/config")
        items = {i["key"]: i for i in resp.json()["data"]}
        assert (items["email.smtp_port"]["min"], items["email.smtp_port"]["max"]) == (
            1,
            65535,
        )
        assert (items["ctf.name"]["min"], items["ctf.name"]["max"]) == (None, None)

    @pytest.mark.parametrize(
        ("key", "value"), [("ctf.team_size", "0"), ("email.smtp_port", "70000")]
    )
    async def test_out_of_range_save_is_refused(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        key: str,
        value: str,
    ) -> None:
        c, _ = admin_client
        resp = await c.put("/admin/config", json={"items": {key: value}})
        assert resp.status_code == 422
        assert key in resp.json()["description"]
        stored = await db_session.execute(
            select(ConfigEntry).where(ConfigEntry.key == key)
        )
        assert stored.scalar_one_or_none() is None


class TestPublicInfoInvalidation:
    async def test_info_dropped_before_clients_are_told(
        self,
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = admin_client
        calls: list[str] = []

        async def _invalidate(*_args) -> None:
            calls.append("invalidate")

        async def _publish(*_args) -> None:
            calls.append("publish")

        with (
            patch("nexctf.module.config.invalidate_info", _invalidate),
            patch("nexctf.module.config.publish_event", _publish),
        ):
            resp = await c.put(
                "/admin/config", json={"items": {"ctf.name": "Renamed CTF"}}
            )
        assert resp.status_code == 200
        assert calls[:2] == ["invalidate", "publish"]


class TestEventTimeOrder:
    """Start, freeze and end times must be saved in order."""

    @pytest.fixture
    def config_overrides(self) -> dict[str, str]:
        return {
            "ctf.start_time": "2099-01-01T00:00:00+00:00",
            "ctf.end_time": "2099-01-03T00:00:00+00:00",
        }

    @pytest.mark.parametrize(
        ("items", "error"),
        [
            (
                {"ctf.end_time": "2098-12-31T00:00:00+00:00"},
                "ctf.end_time: must be after ctf.start_time",
            ),
            (
                {"ctf.freeze_time": "2099-01-04T00:00:00+00:00"},
                "ctf.end_time: must be after ctf.freeze_time",
            ),
        ],
    )
    async def test_out_of_order_times_rejected(
        self,
        admin_client: tuple[AsyncClient, User],
        items: dict[str, str],
        error: str,
    ) -> None:
        c, _ = admin_client
        resp = await c.put("/admin/config", json={"items": items})
        assert resp.status_code == 422
        assert error in resp.json()["description"]

    async def test_freeze_inside_event_accepted(
        self,
        admin_client: tuple[AsyncClient, User],
    ) -> None:
        c, _ = admin_client
        with _patch_invalidate():
            resp = await c.put(
                "/admin/config",
                json={"items": {"ctf.freeze_time": "2099-01-02T00:00:00+00:00"}},
            )
        assert resp.status_code == 200

    async def test_unrelated_key_skips_the_check(
        self,
        admin_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        config_overrides["ctf.end_time"] = "2098-01-01T00:00:00+00:00"
        c, _ = admin_client
        resp = await c.put("/admin/config", json={"items": {"ctf.name": "NexCTF"}})
        assert resp.status_code == 200
