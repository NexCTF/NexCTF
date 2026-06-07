"""Tests for /admin/category CRUD endpoints."""

from httpx import AsyncClient

from nexctf.model import ChallengeCategory, User

from ..base import (
    NULL_UUID,
    CreateGuardMixin,
    DeleteGuardMixin,
    GetItemGuardMixin,
    ListGuardMixin,
    UpdateGuardMixin,
)


class TestListCategories(ListGuardMixin):
    PREFIX = "/admin/category"

    async def test_list_empty(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total_count"] == 0
        assert body["data"] == []

    async def test_list_with_items(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_challenge_category: list[ChallengeCategory],
    ) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total_count"] == len(
            fixture_challenge_category
        )


class TestCreateCategory(CreateGuardMixin):
    PREFIX = "/admin/category"

    async def test_create_success(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={"slug": "web", "name": "Web"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["slug"] == "web"
        assert data["name"] == "Web"
        assert "id" in data

    async def test_create_missing_name(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={"slug": "web"})
        assert resp.status_code == 422

    async def test_create_missing_slug(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={"name": "Web"})
        assert resp.status_code == 422


class TestGetCategory(GetItemGuardMixin):
    PREFIX = "/admin/category"

    async def test_get_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_challenge_category: list[ChallengeCategory],
    ) -> None:
        c, _ = admin_client
        cat = fixture_challenge_category[0]
        resp = await c.get(f"{self.PREFIX}/{cat.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["slug"] == cat.slug
        assert data["name"] == cat.name
        assert data["id"] == str(cat.id)

    async def test_get_not_found(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404


class TestUpdateCategory(UpdateGuardMixin):
    PREFIX = "/admin/category"

    async def test_update_name(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_challenge_category: list[ChallengeCategory],
    ) -> None:
        c, _ = admin_client
        cat = fixture_challenge_category[0]
        resp = await c.put(
            f"{self.PREFIX}/{cat.id}",
            json={"id": str(cat.id), "name": "Web Security"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "Web Security"
        assert data["slug"] == cat.slug

    async def test_update_slug(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_challenge_category: list[ChallengeCategory],
    ) -> None:
        c, _ = admin_client
        cat = fixture_challenge_category[0]
        resp = await c.put(
            f"{self.PREFIX}/{cat.id}",
            json={"id": str(cat.id), "slug": "new-slug"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["slug"] == "new-slug"

    async def test_update_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.put(
            f"{self.PREFIX}/{NULL_UUID}",
            json={"id": NULL_UUID, "name": "X"},
        )
        assert resp.status_code == 404


class TestDeleteCategory(DeleteGuardMixin):
    PREFIX = "/admin/category"

    async def test_delete_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_challenge_category: list[ChallengeCategory],
    ) -> None:
        c, _ = admin_client
        cat = fixture_challenge_category[0]
        resp = await c.delete(f"{self.PREFIX}/{cat.id}")
        assert resp.status_code == 200

        resp2 = await c.get(f"{self.PREFIX}/{cat.id}")
        assert resp2.status_code == 404

    async def test_delete_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 200  # delete is idempotent
