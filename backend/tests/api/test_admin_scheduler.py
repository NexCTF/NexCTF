"""Tests for cron handling on the /admin/scheduler endpoints."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from nexctf.model import User

PREFIX = "/admin/scheduler"
_PARAMS = {"title": "t", "content": "c", "is_broadcast": True, "team_ids": []}


def _payload(**overrides: object) -> dict:
    return {
        "name": "nightly",
        "job_type": "send_notification",
        "params": _PARAMS,
        **overrides,
    }


class TestCronValidation:
    async def test_create_with_cron_derives_first_fire(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            PREFIX + "/jobs", json=_payload(cron_expression="*/5 * * * *")
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["cron_expression"] == "*/5 * * * *"
        assert datetime.fromisoformat(data["scheduled_at"]) > datetime.now(UTC)

    async def test_create_without_cron_or_date_is_rejected(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(PREFIX + "/jobs", json=_payload())
        assert resp.status_code == 422

    async def test_create_with_invalid_cron_is_rejected(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            PREFIX + "/jobs", json=_payload(cron_expression="0 0 30 2 *")
        )
        assert resp.status_code == 422

    async def test_update_sets_and_clears_cron(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        scheduled_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        created = await c.post(
            PREFIX + "/jobs", json=_payload(scheduled_at=scheduled_at)
        )
        job_id = created.json()["data"]["id"]

        resp = await c.put(
            f"{PREFIX}/jobs/{job_id}", json={"cron_expression": "0 3 * * *"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["cron_expression"] == "0 3 * * *"

        resp = await c.put(f"{PREFIX}/jobs/{job_id}", json={"cron_expression": None})
        assert resp.status_code == 200
        assert resp.json()["data"]["cron_expression"] is None

    async def test_update_with_invalid_cron_is_rejected(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        scheduled_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        created = await c.post(
            PREFIX + "/jobs", json=_payload(scheduled_at=scheduled_at)
        )
        job_id = created.json()["data"]["id"]

        resp = await c.put(f"{PREFIX}/jobs/{job_id}", json={"cron_expression": "nope"})
        assert resp.status_code == 422


class TestCronPreview:
    async def test_preview_returns_ascending_fire_times(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.get(PREFIX + "/cron/next", params={"expr": "*/5 * * * *"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["timezone"] == "UTC"
        fires = [datetime.fromisoformat(v) for v in data["next_runs"]]
        assert len(fires) == 3
        assert fires == sorted(fires)
        assert fires[0] > datetime.now(UTC)

    async def test_preview_rejects_invalid_expression(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.get(PREFIX + "/cron/next", params={"expr": "@daily"})
        assert resp.status_code == 422


class TestCronRebase:
    async def test_changing_cron_rebases_the_next_fire(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        created = await c.post(
            PREFIX + "/jobs", json=_payload(cron_expression="0 0 1 1 *")
        )
        job_id = created.json()["data"]["id"]
        far_future = datetime.fromisoformat(created.json()["data"]["scheduled_at"])
        assert far_future > datetime.now(UTC) + timedelta(days=30)

        resp = await c.put(
            f"{PREFIX}/jobs/{job_id}", json={"cron_expression": "*/5 * * * *"}
        )
        assert resp.status_code == 200
        rebased = datetime.fromisoformat(resp.json()["data"]["scheduled_at"])
        assert rebased < datetime.now(UTC) + timedelta(minutes=10)

    async def test_editing_params_only_keeps_the_next_fire(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        created = await c.post(
            PREFIX + "/jobs", json=_payload(cron_expression="0 0 1 1 *")
        )
        job_id = created.json()["data"]["id"]
        scheduled_at = created.json()["data"]["scheduled_at"]

        resp = await c.put(
            f"{PREFIX}/jobs/{job_id}", json={"params": {**_PARAMS, "title": "new"}}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["scheduled_at"] == scheduled_at

    async def test_an_explicit_scheduled_at_survives_a_cron_change(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        """The admin picking a first-run date must win over the derived one."""
        c, _ = admin_client
        created = await c.post(
            PREFIX + "/jobs", json=_payload(cron_expression="0 0 1 1 *")
        )
        job_id = created.json()["data"]["id"]
        chosen = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        resp = await c.put(
            f"{PREFIX}/jobs/{job_id}",
            json={"cron_expression": "*/5 * * * *", "scheduled_at": chosen},
        )
        assert resp.status_code == 200
        assert datetime.fromisoformat(
            resp.json()["data"]["scheduled_at"]
        ) == datetime.fromisoformat(chosen)

    async def test_resending_the_same_cron_keeps_the_next_fire(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        created = await c.post(
            PREFIX + "/jobs", json=_payload(cron_expression="0 0 1 1 *")
        )
        job_id = created.json()["data"]["id"]
        override = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

        resp = await c.put(
            f"{PREFIX}/jobs/{job_id}",
            json={"cron_expression": "0 0 1 1 *", "scheduled_at": override},
        )
        assert resp.status_code == 200
        assert datetime.fromisoformat(
            resp.json()["data"]["scheduled_at"]
        ) == datetime.fromisoformat(override)


class TestTaskHistory:
    async def test_history_of_an_unknown_job_is_404(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.get(f"{PREFIX}/jobs/{uuid4()}/tasks")
        assert resp.status_code == 404

    async def test_history_is_scoped_to_its_own_job(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        scheduled_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        mine = (
            await c.post(PREFIX + "/jobs", json=_payload(scheduled_at=scheduled_at))
        ).json()["data"]["id"]
        other = (
            await c.post(PREFIX + "/jobs", json=_payload(scheduled_at=scheduled_at))
        ).json()["data"]["id"]
        for job_id in (mine, mine, other):
            assert (await c.post(f"{PREFIX}/jobs/{job_id}/run")).status_code == 200

        resp = await c.get(f"{PREFIX}/jobs/{mine}/tasks")
        assert resp.status_code == 200
        rows = resp.json()["data"]
        assert len(rows) == 2
        assert {r["job_id"] for r in rows} == {mine}

        other_resp = await c.get(f"{PREFIX}/jobs/{other}/tasks")
        assert {r["job_id"] for r in other_resp.json()["data"]} == {other}

    async def test_job_detail_no_longer_embeds_every_task(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        scheduled_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        created = await c.post(
            PREFIX + "/jobs", json=_payload(scheduled_at=scheduled_at)
        )
        job_id = created.json()["data"]["id"]

        resp = await c.get(f"{PREFIX}/jobs/{job_id}")
        assert resp.status_code == 200
        assert "tasks" not in resp.json()["data"]


class TestEventTimezone:
    @pytest.fixture
    def config_overrides(self) -> dict[str, str]:
        return {"ctf.timezone": "Europe/Paris"}

    async def test_preview_reports_the_event_timezone(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.get(PREFIX + "/cron/next", params={"expr": "0 0 * * *"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["timezone"] == "Europe/Paris"

    async def test_first_fire_is_midnight_in_the_event_timezone(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        """Local midnight in Paris is 22:00 or 23:00 UTC, never 00:00."""
        c, _ = admin_client
        created = await c.post(
            PREFIX + "/jobs", json=_payload(cron_expression="0 0 * * *")
        )
        assert created.status_code == 200

        fire = datetime.fromisoformat(created.json()["data"]["scheduled_at"])
        assert fire.astimezone(UTC).hour in (22, 23)
        assert fire.astimezone(ZoneInfo("Europe/Paris")).hour == 0
