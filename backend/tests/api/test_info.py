"""Tests for the public info endpoint."""

import json
from datetime import UTC, datetime

from httpx import AsyncClient


class TestPublicInfo:
    async def test_event_times_carry_their_timezone(
        self, http_client: AsyncClient, config_overrides: dict[str, str]
    ) -> None:
        """A time stored without an offset is UTC, and is published as such."""
        config_overrides["ctf.start_time"] = "2026-10-14T10:00:00"
        config_overrides["ctf.end_time"] = ""

        competition = (await http_client.get("/info")).json()["data"]["competition"]

        assert competition["start_time"] == "2026-10-14T10:00:00+00:00"
        assert competition["end_time"] == ""

    async def test_server_time_is_read_on_every_request(
        self, http_client: AsyncClient, mock_redis
    ) -> None:
        """The cached payload is stamped per request, not when it was cached."""
        first = (await http_client.get("/info")).json()["data"]
        mock_redis.get.return_value = json.dumps(
            {k: v for k, v in first.items() if k != "server_time"}
        )
        before = datetime.now(UTC)

        cached = (await http_client.get("/info")).json()["data"]

        assert datetime.fromisoformat(cached["server_time"]) >= before
