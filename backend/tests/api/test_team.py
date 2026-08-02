"""Tests for the public team profile endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Team, User
from nexctf.model.custom_field import (
    CustomFieldDefinition,
    CustomFieldTarget,
    CustomFieldValue,
)

from ..base import NULL_UUID


class TestGetTeamProfile:
    PREFIX = "/team"

    async def test_not_found(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 404

    async def test_profile(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        team = Team(name="ProfileTeam", country="FR", bracket="student")
        db_session.add(team)
        await db_session.flush()
        db_session.add(User(username="alice", team_id=team.id))
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{team.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "ProfileTeam"
        assert data["country"] == "FR"
        assert data["bracket"] == "student"
        assert [m["username"] for m in data["members"]] == ["alice"]
        assert data["rank"] == 1
        assert data["team_count"] == 1

    async def test_members_hidden(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("NEXCTF_VISIBILITY_SHOW_TEAM_MEMBERS", "false")
        team = Team(name="HiddenMembers")
        db_session.add(team)
        await db_session.flush()
        db_session.add(User(username="bob", team_id=team.id))
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{team.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["members"] is None
        assert data["member_count"] == 1

    async def test_member_custom_fields(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        team = Team(name="FieldTeam")
        db_session.add(team)
        await db_session.flush()
        user = User(username="carol", team_id=team.id)
        public = CustomFieldDefinition(
            name="school", label="School", target=CustomFieldTarget.user
        )
        private = CustomFieldDefinition(
            name="phone",
            label="Phone",
            target=CustomFieldTarget.user,
            is_public=False,
        )
        db_session.add_all([user, public, private])
        await db_session.flush()
        db_session.add_all(
            [
                CustomFieldValue(definition_id=public.id, user_id=user.id, value="MIT"),
                CustomFieldValue(
                    definition_id=private.id, user_id=user.id, value="0600"
                ),
            ]
        )
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{team.id}")
        assert resp.status_code == 200
        member = resp.json()["data"]["members"][0]
        assert member["custom_fields"] == [
            {
                "name": "school",
                "label": "School",
                "field_type": "string",
                "value": "MIT",
            }
        ]

    async def test_invite_code_hidden(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        team = Team(name="SecretTeam", invite_code="ABCD1234")
        db_session.add(team)
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{team.id}")
        assert "invite_code" not in resp.json()["data"]
