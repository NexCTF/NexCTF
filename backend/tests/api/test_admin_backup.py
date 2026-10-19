"""Tests for downloading a backup through a one-time ticket."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from nexctf.model import Event

KEY = "backups/nexctf-20260908T143005Z-manual.dump"


@pytest.fixture(autouse=True)
def ticket_store(mock_redis) -> None:
    """Back the mocked Redis ``set``/``getdel`` with a dict."""
    store: dict[str, str] = {}

    async def set_(name: str, value: str, **_: object) -> bool:
        store[name] = value
        return True

    async def getdel(name: str) -> str | None:
        return store.pop(name, None)

    mock_redis.set = AsyncMock(side_effect=set_)
    mock_redis.getdel = AsyncMock(side_effect=getdel)


@asynccontextmanager
async def _stream(key: str) -> AsyncGenerator[AsyncIterator[bytes]]:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"dump"

    yield chunks()


async def _ticket(c: AsyncClient) -> str:
    resp = await c.post("/admin/backup/download", params={"key": KEY})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["ticket"]


async def _download(c: AsyncClient, ticket: str):
    with patch("nexctf.core.s3.stream", _stream):
        return await c.get("/admin/backup/download", params={"ticket": ticket})


class TestDownload:
    async def test_streams_the_ticketed_dump(self, admin_client):
        c, _ = admin_client
        resp = await _download(c, await _ticket(c))

        assert resp.status_code == 200
        assert resp.content == b"dump"
        assert KEY.removeprefix("backups/") in resp.headers["content-disposition"]

    async def test_ticket_is_single_use(self, admin_client):
        c, _ = admin_client
        ticket = await _ticket(c)

        assert (await _download(c, ticket)).status_code == 200
        assert (await _download(c, ticket)).status_code == 404

    async def test_unknown_ticket(self, admin_client):
        c, _ = admin_client
        assert (await _download(c, "unknown")).status_code == 404

    async def test_rejects_a_non_backup_key(self, admin_client):
        c, _ = admin_client
        resp = await c.post("/admin/backup/download", params={"key": "backups/../x"})
        assert resp.status_code == 400

    async def test_is_audited(self, admin_client, db_session):
        c, _ = admin_client
        await _ticket(c)

        event = (
            await db_session.execute(
                select(Event).where(Event.event_type == "backup.downloaded")
            )
        ).scalar_one()
        assert event.target_label == KEY

    async def test_players_cannot_download(self, user_client):
        c, _ = user_client
        resp = await c.post("/admin/backup/download", params={"key": KEY})
        assert resp.status_code == 403
