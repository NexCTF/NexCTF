"""Tests for the team membership endpoints and the team-changes lock."""

from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Submission, Team, User
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from tests.base import make_solvable, make_team, make_user, put_in_team


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

    async def test_inactive_members_do_not_take_a_seat(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        client, _ = user_client
        team = await make_team(db_session, "HasBanned")
        await make_user(db_session, "active1", team)
        db_session.add(User(username="banned1", team_id=team.id, is_active=False))
        await db_session.flush()
        config_overrides["ctf.team_size"] = "2"

        resp = await client.post("/me/team/join", json={"code": team.invite_code})
        assert resp.status_code == 200

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


class TestTeamCreation:
    async def test_create_rejects_a_taken_name(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """The unique index rejects the create as a 409, not an unhandled 500."""
        client, user = user_client
        db_session.add(Team(name="Taken", invite_code="TAKEN001"))
        await db_session.flush()

        resp = await client.post("/me/team", json={"name": "Taken"})
        assert resp.status_code == 409
        assert user.team_id is None


class TestLeavingAfterScoring:
    async def test_a_team_that_scored_cannot_be_left(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Its members would otherwise re-score the same flags for another team."""
        client, user = user_client
        _, question = await make_solvable(db_session, user, "flag")
        db_session.add(
            Submission(
                team_id=user.team_id,
                question_id=question.id,
                answer="flag",
                is_correct=True,
            )
        )
        await db_session.flush()

        resp = await client.post("/me/team/leave")
        assert resp.json()["error_code"] == "TEAM-409-SCORED"
        assert user.team_id is not None

    async def test_wrong_answers_do_not_hold_a_member(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, user = user_client
        _, question = await make_solvable(db_session, user, "flag")
        db_session.add(
            Submission(team_id=user.team_id, question_id=question.id, answer="x")
        )
        await db_session.flush()

        assert (await client.post("/me/team/leave")).status_code == 204


class TestEmptyTeamCleanup:
    async def test_last_member_leaving_an_unplayed_team_deletes_it(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, user = user_client
        team = await put_in_team(db_session, user)

        assert (await client.post("/me/team/leave")).status_code == 204
        assert await db_session.get(Team, team.id) is None

    async def test_a_team_with_submissions_is_kept(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, user = user_client
        _, question = await make_solvable(db_session, user, "flag")
        team_id = user.team_id
        db_session.add(Submission(team_id=team_id, question_id=question.id, answer="x"))
        await db_session.flush()

        assert (await client.post("/me/team/leave")).status_code == 204
        assert await db_session.get(Team, team_id) is not None

    async def test_a_team_with_members_left_is_kept(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, user = user_client
        team = await put_in_team(db_session, user)
        await make_user(db_session, "stays", team)

        assert (await client.post("/me/team/leave")).status_code == 204
        assert await db_session.get(Team, team.id) is not None


class TestTeamNames:
    async def test_names_ignore_letter_case(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, _ = user_client
        db_session.add(Team(name="Taken", invite_code="CASED001"))
        await db_session.flush()

        assert (
            await client.post("/me/team", json={"name": "TAKEN"})
        ).status_code == 409

    async def test_blank_name_is_refused(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        client, _ = user_client
        assert (await client.post("/me/team", json={"name": "   "})).status_code == 422


class TestTeamChanges:
    async def test_leave(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        client, user = user_client
        await put_in_team(db_session, user)

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
        team = await put_in_team(db_session, user)
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
        team = await put_in_team(db_session, user)
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
        team = await put_in_team(db_session, user)
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


class TestStreamsFollowMembership:
    async def test_joining_closes_the_old_streams(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Open streams still carry the old team's channel until they reconnect."""
        client, user = user_client
        team = await make_team(db_session, "Joinable")
        close = AsyncMock()

        with patch("nexctf.api.routes.me.close_user_streams", close):
            resp = await client.post("/me/team/join", json={"code": team.invite_code})
        assert resp.is_success
        close.assert_awaited_once_with(ANY, user.id)
