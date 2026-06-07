"""Tests for /admin/oauth-provider CRUD endpoints."""

from httpx import AsyncClient

from nexctf.model import OAuthProvider, User

from ..base import (
    NULL_UUID,
    CreateGuardMixin,
    DeleteGuardMixin,
    GetItemGuardMixin,
    ListGuardMixin,
    UpdateGuardMixin,
)

_VALID_PAYLOAD = {
    "slug": "new-idp",
    "name": "New IdP",
    "client_id": "client123",
    "client_secret": "secret123",
    "discovery_url": "https://idp.example.com/.well-known/openid-configuration",
}


class TestListOAuthProviders(ListGuardMixin):
    PREFIX = "/admin/oauth-provider"

    async def test_list_empty(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_list_with_items(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_provider: list[OAuthProvider],
    ) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total_count"] == len(fixture_oauth_provider)


class TestCreateOAuthProvider(CreateGuardMixin):
    PREFIX = "/admin/oauth-provider"

    async def test_create_success(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json=_VALID_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["slug"] == "new-idp"
        assert data["name"] == "New IdP"
        assert "id" in data

    async def test_create_missing_required(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={"slug": "only-slug"})
        assert resp.status_code == 422


class TestGetOAuthProvider(GetItemGuardMixin):
    PREFIX = "/admin/oauth-provider"

    async def test_get_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_provider: list[OAuthProvider],
    ) -> None:
        c, _ = admin_client
        p = fixture_oauth_provider[0]
        resp = await c.get(f"{self.PREFIX}/{p.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["slug"] == p.slug
        assert data["id"] == str(p.id)

    async def test_get_not_found(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404


class TestUpdateOAuthProvider(UpdateGuardMixin):
    PREFIX = "/admin/oauth-provider"

    async def test_update_name(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_provider: list[OAuthProvider],
    ) -> None:
        c, _ = admin_client
        p = fixture_oauth_provider[0]
        resp = await c.put(
            f"{self.PREFIX}/{p.id}",
            json={"id": str(p.id), "name": "Renamed IdP"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Renamed IdP"

    async def test_update_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.put(f"{self.PREFIX}/{NULL_UUID}", json={"id": NULL_UUID})
        assert resp.status_code == 404


class TestDeleteOAuthProvider(DeleteGuardMixin):
    PREFIX = "/admin/oauth-provider"

    async def test_delete_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_oauth_provider: list[OAuthProvider],
    ) -> None:
        c, _ = admin_client
        p = fixture_oauth_provider[0]
        resp = await c.delete(f"{self.PREFIX}/{p.id}")
        assert resp.status_code == 200

        resp2 = await c.get(f"{self.PREFIX}/{p.id}")
        assert resp2.status_code == 404

    async def test_delete_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 200
