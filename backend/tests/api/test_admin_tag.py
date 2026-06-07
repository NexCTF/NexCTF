"""Tests for /admin/tag CRUD endpoints."""

from httpx import AsyncClient

from nexctf.model import Tag, User

from ..base import (
    NULL_UUID,
    CreateGuardMixin,
    DeleteGuardMixin,
    GetItemGuardMixin,
    ListGuardMixin,
    UpdateGuardMixin,
)

_NEW_TAG = {
    "name": "Critical",
    "description": "Critical challenges",
    "color": "#ff0000",
}


class TestListTags(ListGuardMixin):
    PREFIX = "/admin/tag"

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
        fixture_tag: list[Tag],
    ) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total_count"] == len(fixture_tag)


class TestCreateTag(CreateGuardMixin):
    PREFIX = "/admin/tag"

    async def test_create_success(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json=_NEW_TAG)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == _NEW_TAG["name"]
        assert data["description"] == _NEW_TAG["description"]
        assert data["color"] == _NEW_TAG["color"]
        assert "id" in data

    async def test_create_missing_field(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={"name": "Easy"})
        assert resp.status_code == 422


class TestGetTag(GetItemGuardMixin):
    PREFIX = "/admin/tag"

    async def test_get_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_tag: list[Tag],
    ) -> None:
        c, _ = admin_client
        t = fixture_tag[0]
        resp = await c.get(f"{self.PREFIX}/{t.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == t.name
        assert data["id"] == str(t.id)

    async def test_get_not_found(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404


class TestUpdateTag(UpdateGuardMixin):
    PREFIX = "/admin/tag"

    async def test_update_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_tag: list[Tag],
    ) -> None:
        c, _ = admin_client
        t = fixture_tag[0]
        resp = await c.put(
            f"{self.PREFIX}/{t.id}",
            json={
                "id": str(t.id),
                "name": t.name,
                "description": "For experts",
                "color": t.color,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["description"] == "For experts"

    async def test_update_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.put(
            f"{self.PREFIX}/{NULL_UUID}",
            json={"id": NULL_UUID, "name": "X", "description": "", "color": "#000"},
        )
        assert resp.status_code == 404


class TestDeleteTag(DeleteGuardMixin):
    PREFIX = "/admin/tag"

    async def test_delete_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_tag: list[Tag],
    ) -> None:
        c, _ = admin_client
        t = fixture_tag[0]
        resp = await c.delete(f"{self.PREFIX}/{t.id}")
        assert resp.status_code == 200

        resp2 = await c.get(f"{self.PREFIX}/{t.id}")
        assert resp2.status_code == 404

    async def test_delete_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 200  # delete is idempotent
