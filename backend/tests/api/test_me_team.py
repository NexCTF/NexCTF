"""Tests for the team membership endpoints and the team-changes lock."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Submission, Team, User
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge


async def _put_in_team(db_session: AsyncSession, user: User) -> Team:
    team = Team(name="MyTeam", invite_code="MYTEAM01")
    db_session.add(team)
    await db_session.flush()
    user.team_id = team.id
    await db_session.flush()
    return team


class TestTeamSize:
    async def test_join_honours_team_size_override(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        """A raised ctf.team_size lets a member join past the code default of 4."""
        client, user = user_client
        team = Team(name="FullTeam", invite_code="FULLTEAM")
        db_session.add(team)
        await db_session.flush()
        for i in range(4):
            db_session.add(
                User(username=f"member{i}", hashed_password="x", team_id=team.id)
            )
        await db_session.flush()
        config_overrides["ctf.team_size"] = "5"

        resp = await client.post("/me/team/join", json={"code": "FULLTEAM"})
        assert resp.status_code == 200
        assert user.team_id == team.id

    async def test_join_rejected_when_team_size_reached(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        client, user = user_client
        team = Team(name="FullTeam", invite_code="FULLTEAM")
        db_session.add(team)
        await db_session.flush()
        db_session.add(User(username="member0", hashed_password="x", team_id=team.id))
        await db_session.flush()
        config_overrides["ctf.team_size"] = "1"

        resp = await client.post("/me/team/join", json={"code": "FULLTEAM"})
        assert resp.status_code == 409
        assert user.team_id is None


class TestTeamChanges:
    async def test_leave(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, user = user_client
        await _put_in_team(db_session, user)

        resp = await client.post("/me/team/leave")
        assert resp.status_code == 204
        assert user.team_id is None

    async def test_leave_locked(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        client, user = user_client
        team = await _put_in_team(db_session, user)
        config_overrides["ctf.allow_team_changes"] = "false"

        resp = await client.post("/me/team/leave")
        assert resp.status_code == 403
        assert user.team_id == team.id

    async def test_join_locked(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        client, user = user_client
        db_session.add(Team(name="LockedTeam", invite_code="LOCKED12"))
        await db_session.flush()
        config_overrides["ctf.allow_team_changes"] = "false"

        resp = await client.post("/me/team/join", json={"code": "LOCKED12"})
        assert resp.status_code == 403
        assert user.team_id is None

    async def test_rotate_invite_code_locked(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        client, user = user_client
        team = await _put_in_team(db_session, user)
        config_overrides["ctf.allow_team_changes"] = "false"

        resp = await client.post("/me/team/invite-code")
        assert resp.status_code == 403
        assert team.invite_code == "MYTEAM01"

    async def test_create_locked(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        client, user = user_client
        config_overrides["ctf.allow_team_changes"] = "false"

        resp = await client.post("/me/team", json={"name": "NewTeam"})
        assert resp.status_code == 403
        assert user.team_id is None

    async def test_create_generates_invite_code(
        self,
        user_client: tuple[AsyncClient, User],
    ) -> None:
        client, _ = user_client

        resp = await client.post("/me/team", json={"name": "NewTeam"})
        assert resp.status_code == 201
        assert len(resp.json()["data"]["invite_code"]) == 8

    async def test_create_ignores_client_supplied_fields(
        self,
        user_client: tuple[AsyncClient, User],
    ) -> None:
        """Server-managed fields in the body must not reach the ORM."""
        client, _ = user_client

        resp = await client.post(
            "/me/team",
            json={"name": "NewTeam", "invite_code": "PWNED123", "bracket": "elite"},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["invite_code"] != "PWNED123"
        assert data["bracket"] is None


class TestMyTeamStaysLive:
    async def test_own_solves_visible_after_freeze(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        """The freeze hides progress from rivals, not from a team's own members."""
        config_overrides["ctf.freeze_time"] = "2020-06-01T00:00:00+00:00"
        client, user = user_client
        team = await _put_in_team(db_session, user)
        challenge = StandardChallenge(title="Frozen", is_active=True)
        db_session.add(challenge)
        await db_session.flush()
        question = Question(label="Q", points=100, challenge_id=challenge.id)
        db_session.add(question)
        await db_session.flush()
        db_session.add(
            Submission(
                team_id=team.id,
                question_id=question.id,
                answer="flag",
                is_correct=True,
                points_earned=100,
                created_at=datetime(2020, 12, 1, tzinfo=UTC),
            )
        )
        await db_session.flush()

        resp = await client.get("/me/team")
        assert resp.status_code == 200
        stats = resp.json()["data"]["challenge_stats"][0]
        assert stats["solved_question_count"] == 1
