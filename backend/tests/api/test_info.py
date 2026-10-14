"""Tests for the public info endpoint."""

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
