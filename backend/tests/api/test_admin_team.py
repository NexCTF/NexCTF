"""Tests for /admin/team CRUD endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import ChallengeFeedback, ScoreAdjustment, Team, User
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge

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

    async def test_create_duplicate_name(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        assert (await c.post(self.PREFIX, json={"name": "dup"})).status_code == 200
        resp = await c.post(self.PREFIX, json={"name": "dup"})
        assert resp.status_code == 409

    async def test_create_with_custom_fields(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        """Values sent on create land in the same transaction as the team."""
        c, _ = admin_client
        dresp = await c.post(
            "/admin/custom-field",
            json={"name": "school", "label": "School", "target": "team"},
        )
        assert dresp.status_code == 200
        definition_id = dresp.json()["data"]["id"]

        resp = await c.post(
            self.PREFIX,
            json={"name": "cf-team", "custom_fields": {definition_id: "MIT"}},
        )
        assert resp.status_code == 200

        detail = await c.get(f"{self.PREFIX}/{resp.json()['data']['id']}/detail")
        values = detail.json()["data"]["custom_field_values"]
        assert [(v["definition"]["id"], v["value"]) for v in values] == [
            (definition_id, "MIT")
        ]

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


class TestTeamRelatedListings:
    PREFIX = "/admin/team"

    async def test_only_this_teams_rows(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
        db_session: AsyncSession,
    ) -> None:
        c, admin = admin_client
        mine, other = fixture_team[0], Team(name="other")
        mine_id = mine.id
        db_session.add(other)
        await db_session.flush()

        ch = StandardChallenge(title="Feedback Filter Test")
        db_session.add(ch)
        await db_session.flush()
        db_session.add(Question(label="Q1", points=1, challenge_id=ch.id))
        db_session.add_all(
            [
                ChallengeFeedback(team_id=mine_id, challenge_id=ch.id, rating=5),
                ChallengeFeedback(team_id=other.id, challenge_id=ch.id, rating=1),
                ScoreAdjustment(
                    team_id=mine_id, amount=10, reason="mine", created_by_id=admin.id
                ),
                ScoreAdjustment(
                    team_id=other.id, amount=-5, reason="other", created_by_id=admin.id
                ),
            ]
        )
        await db_session.flush()

        resp = await c.get(f"{self.PREFIX}/{mine_id}/feedback")
        assert resp.status_code == 200
        assert [fb["rating"] for fb in resp.json()["data"]] == [5]

        resp = await c.get(f"{self.PREFIX}/{mine_id}/score-adjustments")
        assert resp.status_code == 200
        assert [adj["reason"] for adj in resp.json()["data"]] == ["mine"]


class TestGetTeamScore:
    PREFIX = "/admin/team"

    async def test_score_breakdown(
        self,
        admin_client: tuple[AsyncClient, User],
        fixture_team: list[Team],
    ) -> None:
        c, _ = admin_client
        t = fixture_team[0]
        resp = await c.get(f"{self.PREFIX}/{t.id}/score")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["team_name"] == t.name
        assert data["total"] == 0
        assert data["adjustments"] == []

    async def test_score_not_found(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}/score")
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
