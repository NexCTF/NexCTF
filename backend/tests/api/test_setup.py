"""Tests for the first-run setup endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi_multiauth import hash_token
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.security import verify_password
from nexctf.model import Event, User, UserRole
from nexctf.module import setup

from ..base import make_user

TOKEN = "setup-token"
BODY = {
    "token": TOKEN,
    "username": "root",
    "password": "strongpass",
    "email": "root@example.com",
}


@pytest.fixture
def stored_token(mock_redis) -> AsyncMock:
    """Serve TOKEN as the current setup token; returns the mocked delete."""
    mock_redis.get = AsyncMock(return_value=hash_token(TOKEN))
    mock_redis.delete = AsyncMock(return_value=1)
    return mock_redis.delete


async def _users(db_session: AsyncSession) -> list[User]:
    return list((await db_session.execute(select(User))).scalars())


@pytest.fixture(autouse=True)
def setup_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test on an instance that has not seen an admin yet."""
    monkeypatch.setattr(setup, "_admin_seen", False)


class TestSetupGate:
    async def test_api_refuses_requests_until_an_admin_exists(
        self, http_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        resp = await http_client.get("/info/me")
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SETUP-403-REQUIRED"

        await make_user(db_session, "root", role=UserRole.admin)
        assert (await http_client.get("/info")).status_code == 200


class TestSetupStatus:
    async def test_admin_required_until_an_admin_exists(
        self, http_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await make_user(db_session, "player")
        resp = await http_client.get("/setup")
        assert resp.json()["data"] == {"admin_required": True}

        await make_user(db_session, "root", role=UserRole.admin)
        resp = await http_client.get("/setup")
        assert resp.json()["data"] == {"admin_required": False}


class TestCreateFirstAdmin:
    async def test_creates_a_signed_in_admin(
        self, http_client: AsyncClient, db_session: AsyncSession, stored_token
    ) -> None:
        resp = await http_client.post("/setup/admin", json=BODY)

        assert resp.status_code == 204
        assert "NexCTF" in resp.cookies
        (user,) = await _users(db_session)
        assert user.role is UserRole.admin
        assert user.email_verified is True
        assert user.hashed_password is not None
        assert verify_password("strongpass", user.hashed_password)
        stored_token.assert_awaited_once()
        event = (
            await db_session.execute(
                select(Event).where(Event.event_type == "admin.user_created")
            )
        ).scalar_one()
        assert event.meta["source"] == "setup"
        assert event.meta["target_username"] == "root"

    @pytest.mark.parametrize("token", ["wrong-token", ""])
    async def test_rejects_a_wrong_token(
        self, http_client: AsyncClient, db_session: AsyncSession, stored_token, token
    ) -> None:
        resp = await http_client.post("/setup/admin", json={**BODY, "token": token})

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SETUP-403-TOKEN"
        assert await _users(db_session) == []
        stored_token.assert_not_awaited()

    async def test_rejects_when_no_token_was_issued(
        self, http_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        resp = await http_client.post("/setup/admin", json=BODY)

        assert resp.status_code == 403
        assert await _users(db_session) == []

    async def test_closed_once_an_admin_exists(
        self, http_client: AsyncClient, db_session: AsyncSession, stored_token
    ) -> None:
        await make_user(db_session, "admin", role=UserRole.admin)

        resp = await http_client.post("/setup/admin", json=BODY)

        assert resp.status_code == 409
        assert resp.json()["error_code"] == "SETUP-409-DONE"
        stored_token.assert_not_awaited()

    async def test_taken_username_keeps_the_token(
        self, http_client: AsyncClient, db_session: AsyncSession, stored_token
    ) -> None:
        await make_user(db_session, "root")

        resp = await http_client.post("/setup/admin", json=BODY)

        assert resp.status_code == 409
        stored_token.assert_not_awaited()

    async def test_refuses_when_the_token_was_used_meanwhile(
        self, http_client: AsyncClient, mock_redis, stored_token
    ) -> None:
        mock_redis.delete = AsyncMock(return_value=0)

        resp = await http_client.post("/setup/admin", json=BODY)

        assert resp.status_code == 403
        assert "NexCTF" not in resp.cookies

    async def test_rejects_a_weak_password(
        self, http_client: AsyncClient, stored_token
    ) -> None:
        resp = await http_client.post(
            "/setup/admin", json={**BODY, "password": "short"}
        )

        assert resp.status_code == 422
