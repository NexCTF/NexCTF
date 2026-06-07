"""Tests for /admin/oauth-client CRUD endpoints."""

from httpx import AsyncClient

from nexctf.model import User
from nexctf.model.oauth_server import OAuthServerClient

from ..base import (
    NULL_UUID,
    CreateGuardMixin,
    DeleteGuardMixin,
    GetItemGuardMixin,
    ListGuardMixin,
    UpdateGuardMixin,
)

_VALID_PAYLOAD = {
    "name": "My App",
    "redirect_uris": "https://app.example.com/callback",
}


class TestListOAuthClients(ListGuardMixin):
    PREFIX = "/admin/oauth-client"

    async def test_list_empty(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_list_with_items(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total_count"] == len(
            fixture_oauth_server_client
        )


class TestCreateOAuthClient(CreateGuardMixin):
    PREFIX = "/admin/oauth-client"

    async def test_create_success(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json=_VALID_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "My App"
        assert data["client_id"].startswith("nexctf_")
        assert "client_secret" in data
        assert len(data["client_secret"]) > 10

    async def test_create_secret_not_in_subsequent_get(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        create_resp = await c.post(self.PREFIX, json=_VALID_PAYLOAD)
        assert create_resp.status_code == 200
        client_uuid = create_resp.json()["data"]["id"]

        get_resp = await c.get(f"{self.PREFIX}/{client_uuid}")
        assert get_resp.status_code == 200
        assert "client_secret" not in get_resp.json()["data"]

    async def test_create_missing_redirect_uris(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={"name": "no-redirect"})
        assert resp.status_code == 422


class TestGetOAuthClient(GetItemGuardMixin):
    PREFIX = "/admin/oauth-client"

    async def test_get_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        c, _ = admin_client
        client = fixture_oauth_server_client[0]
        resp = await c.get(f"{self.PREFIX}/{client.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == client.name
        assert data["client_id"] == client.client_id
        assert "client_secret" not in data

    async def test_get_not_found(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404


class TestUpdateOAuthClient(UpdateGuardMixin):
    PREFIX = "/admin/oauth-client"

    async def test_update_name(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        c, _ = admin_client
        client = fixture_oauth_server_client[0]
        resp = await c.put(
            f"{self.PREFIX}/{client.id}",
            json={"name": "Renamed App"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Renamed App"

    async def test_update_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.put(f"{self.PREFIX}/{NULL_UUID}", json={"name": "x"})
        assert resp.status_code == 404


class TestDeleteOAuthClient(DeleteGuardMixin):
    PREFIX = "/admin/oauth-client"

    async def test_delete_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        c, _ = admin_client
        client = fixture_oauth_server_client[0]
        resp = await c.delete(f"{self.PREFIX}/{client.id}")
        assert resp.status_code == 200

        resp2 = await c.get(f"{self.PREFIX}/{client.id}")
        assert resp2.status_code == 404

    async def test_delete_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 200
