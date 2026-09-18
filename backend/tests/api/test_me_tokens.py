"""API-token last-used tracking on /me/tokens."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.security import create_api_token
from nexctf.model import User, UserRole


@pytest.fixture
def token_client(client_factory, db_session: AsyncSession, override_db_context):
    """Build a client authenticated by a bearer token, with its token row."""

    @asynccontextmanager
    async def _make(scopes: list[str]):
        user = User(username="token_owner", role=UserRole.user)
        db_session.add(user)
        await db_session.flush()
        raw, row = await create_api_token(user.id, scopes=scopes)
        async with client_factory() as client:
            client.headers["Authorization"] = f"Bearer {raw}"
            yield client, row

    return _make


class TestTokenLastUsed:
    async def test_starts_unused(self, token_client) -> None:
        async with token_client(["read:token"]) as (_, row):
            assert row.last_used_at is None

    async def test_authenticated_request_stamps_last_used(self, token_client) -> None:
        async with token_client(["read:token"]) as (client, row):
            assert (await client.get("/me/tokens")).status_code == 200
            assert row.last_used_at is not None

    async def test_stamp_is_throttled(self, token_client) -> None:
        async with token_client(["read:token"]) as (client, row):
            await client.get("/me/tokens")
            stamped_at = row.last_used_at
            await client.get("/me/tokens")
            assert row.last_used_at == stamped_at

    async def test_stale_stamp_is_refreshed(self, token_client) -> None:
        async with token_client(["read:token"]) as (client, row):
            stale = datetime.now(UTC) - timedelta(hours=1)
            row.last_used_at = stale
            await client.get("/me/tokens")
            assert row.last_used_at is not None
            assert row.last_used_at > stale

    async def test_listing_exposes_last_used(self, token_client) -> None:
        async with token_client(["read:token"]) as (client, _):
            resp = await client.get("/me/tokens")
            assert resp.status_code == 200
            item = resp.json()["data"][0]
            assert "last_used_at" in item


class TestTokenRejectedRequests:
    async def test_admin_route_refuses_a_user_token(self, token_client) -> None:
        async with token_client(["read:admin.user"]) as (client, _):
            assert (await client.get("/admin/user")).status_code == 403


class TestTokenListingShape:
    async def test_created_token_reports_never_used(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        client, _ = user_client
        resp = await client.post(
            "/me/tokens", json={"name": "ci", "scopes": ["read:token"]}
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["last_used_at"] is None
