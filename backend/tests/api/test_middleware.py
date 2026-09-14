"""Tests for the request context middleware."""

import logging

from fastapi_toolsets.logger import ACCESS_LOGGER
from httpx import AsyncClient

from nexctf.model import User


class TestRequestContext:
    """Every request carries an id, in the response and in its log records."""

    async def test_each_request_gets_its_own_id(self, http_client: AsyncClient) -> None:
        first = await http_client.get("/scoreboard")
        second = await http_client.get("/scoreboard")
        assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]

    async def test_access_line_carries_the_request_fields(
        self, http_client: AsyncClient, context_caplog
    ) -> None:
        with context_caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
            resp = await http_client.get("/scoreboard")

        record = next(r for r in context_caplog.records if r.name == ACCESS_LOGGER)
        assert record.method == "GET"
        assert record.path.endswith("/scoreboard")
        assert record.status == 200
        assert record.request_id == resp.headers["X-Request-ID"]
        assert record.client_ip
        assert isinstance(record.duration_ms, float)

    async def test_optionally_authenticated_request_carries_the_user(
        self, user_client: tuple[AsyncClient, User], context_caplog
    ) -> None:
        client, user = user_client
        with context_caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
            await client.get("/scoreboard")

        record = next(r for r in context_caplog.records if r.name == ACCESS_LOGGER)
        assert record.user_id == str(user.id)
        assert record.username == user.username


class TestHealthCheck:
    """Local /info checks stay out of the access log, proxied ones do not."""

    async def test_local_check_is_not_logged(
        self, http_client: AsyncClient, caplog
    ) -> None:
        with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
            resp = await http_client.get("/info")

        assert resp.status_code == 200
        assert "X-Request-ID" not in resp.headers
        assert not [r for r in caplog.records if r.name == ACCESS_LOGGER]

    async def test_proxied_info_is_logged(
        self, http_client: AsyncClient, caplog
    ) -> None:
        with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
            resp = await http_client.get(
                "/info", headers={"X-Forwarded-For": "203.0.113.7"}
            )

        assert resp.headers["X-Request-ID"]
        assert [r for r in caplog.records if r.name == ACCESS_LOGGER]

    async def test_other_local_paths_are_logged(
        self, http_client: AsyncClient, caplog
    ) -> None:
        with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
            await http_client.get("/info/me")

        assert [r for r in caplog.records if r.name == ACCESS_LOGGER]
