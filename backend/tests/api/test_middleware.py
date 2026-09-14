"""Tests for the request context middleware."""

import logging

from httpx import AsyncClient

from nexctf.core.logging import ACCESS_LOGGER, ContextFilter


class TestRequestContext:
    """Every request carries an id, in the response and in its log records."""

    async def test_response_carries_a_request_id(
        self, http_client: AsyncClient
    ) -> None:
        resp = await http_client.get("/info")
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"]

    async def test_each_request_gets_its_own_id(self, http_client: AsyncClient) -> None:
        first = await http_client.get("/info")
        second = await http_client.get("/info")
        assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]

    async def test_access_line_carries_the_request_fields(
        self, http_client: AsyncClient, caplog
    ) -> None:
        caplog.handler.addFilter(ContextFilter())
        with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
            resp = await http_client.get("/info")

        record = next(r for r in caplog.records if r.name == ACCESS_LOGGER)
        assert record.method == "GET"
        assert record.path.endswith("/info")
        assert record.status == 200
        assert record.request_id == resp.headers["X-Request-ID"]
        assert isinstance(record.duration_ms, float)
