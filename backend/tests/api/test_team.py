"""Tests for the public team profile endpoint."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Submission, Team, User
from nexctf.model.custom_field import (
    CustomFieldDefinition,
    CustomFieldTarget,
    CustomFieldValue,
)
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge

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

    async def test_solves_after_freeze_hidden(
        self,
        http_client: AsyncClient,
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        """Post-freeze progress must not leak through the public profile."""
        config_overrides["ctf.freeze_time"] = "2020-06-01T00:00:00+00:00"
        team = Team(name="FrozenTeam")
        challenge = StandardChallenge(title="Frozen", is_active=True)
        db_session.add_all([team, challenge])
        await db_session.flush()
        early = Question(label="Q1", points=100, index=0, challenge_id=challenge.id)
        late = Question(label="Q2", points=100, index=1, challenge_id=challenge.id)
        db_session.add_all([early, late])
        await db_session.flush()
        db_session.add_all(
            [
                Submission(
                    team_id=team.id,
                    question_id=early.id,
                    answer="flag",
                    is_correct=True,
                    points_earned=100,
                    created_at=datetime(2020, 1, 1, tzinfo=UTC),
                ),
                Submission(
                    team_id=team.id,
                    question_id=late.id,
                    answer="flag",
                    is_correct=True,
                    points_earned=100,
                    created_at=datetime(2020, 12, 1, tzinfo=UTC),
                ),
            ]
        )
        await db_session.flush()

        resp = await http_client.get(f"{self.PREFIX}/{team.id}")
        assert resp.status_code == 200
        stats = resp.json()["data"]["challenge_stats"][0]
        solved = {q["question_id"]: q["is_solved"] for q in stats["questions"]}
        assert solved == {str(early.id): True, str(late.id): False}
        assert stats["solved_question_count"] == 1
        assert stats["points_earned"] == 100
        assert stats["last_solve_at"].startswith("2020-01-01")

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
