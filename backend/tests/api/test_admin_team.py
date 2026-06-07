"""Tests for /admin/team CRUD endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Team, User

from ..base import (
    NULL_UUID,
    CreateGuardMixin,
    DeleteGuardMixin,
    GetItemGuardMixin,
    ListGuardMixin,
    UpdateGuardMixin,
)


class TestListTeams(ListGuardMixin):
    PREFIX = "/admin/team"

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
        fixture_team: list[Team],
    ) -> None:
        c, _ = admin_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total_count"] == len(fixture_team)


class TestCreateTeam(CreateGuardMixin):
    PREFIX = "/admin/team"

    async def test_create_success(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={"name": "alpha"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "alpha"
        assert "id" in data

    async def test_create_missing_name(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(self.PREFIX, json={})
        assert resp.status_code == 422


class TestGetTeam(GetItemGuardMixin):
    PREFIX = "/admin/team"

    async def test_get_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
    ) -> None:
        c, _ = admin_client
        t = fixture_team[0]
        resp = await c.get(f"{self.PREFIX}/{t.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == t.name
        assert data["id"] == str(t.id)

    async def test_get_not_found(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404


class TestGetTeamDetail:
    PREFIX = "/admin/team"

    async def test_detail_empty_team(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
    ) -> None:
        # fixture_team only — no users inserted, so team has no members
        c, _ = admin_client
        t = fixture_team[0]
        resp = await c.get(f"{self.PREFIX}/{t.id}/detail")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == t.name
        assert data["users"] == []

    async def test_detail_with_members(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
        fixture_user_members: list[User],
        db_session: AsyncSession,
    ) -> None:
        c, _ = admin_client
        t = fixture_team[0]
        t_id = (
            t.id
        )  # capture before expire() to avoid MissingGreenlet on sync attr access
        db_session.expire(t)
        resp = await c.get(f"{self.PREFIX}/{t_id}/detail")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["users"]) == len(fixture_user_members)

    async def test_detail_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}/detail")
        assert resp.status_code == 404


class TestUpdateTeam(UpdateGuardMixin):
    PREFIX = "/admin/team"

    async def test_update_name(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
    ) -> None:
        c, _ = admin_client
        t = fixture_team[0]
        resp = await c.put(
            f"{self.PREFIX}/{t.id}",
            json={"id": str(t.id), "name": "new-name"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "new-name"

    async def test_update_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.put(
            f"{self.PREFIX}/{NULL_UUID}", json={"id": NULL_UUID, "name": "x"}
        )
        assert resp.status_code == 404


class TestDeleteTeam(DeleteGuardMixin):
    PREFIX = "/admin/team"

    async def test_delete_success(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
    ) -> None:
        # fixture_team only — no users reference this team, safe to delete
        c, _ = admin_client
        t = fixture_team[0]
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
