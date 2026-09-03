"""Tests for challenge endpoint event-timing guards."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_object_session

from nexctf.api.routes.challenge import _writeup_visible
from nexctf.model import HintUnlock, Team, User
from nexctf.model.question import Hint, Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution
from tests.base import put_in_team

NULL_UUID = "00000000-0000-0000-0000-000000000000"

FUTURE = "2099-01-01T00:00:00+00:00"
PAST = "2000-01-01T00:00:00+00:00"


# ── list challenges ────────────────────────────────────────────────────────────


class TestListChallengesBeforeStart:
    async def test_user_blocked_when_start_in_future(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Regular users cannot list challenges before the CTF starts."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 403

    async def test_admin_bypasses_start_check(
        self,
        admin_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Admins can list challenges before the CTF starts."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, _ = admin_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200

    async def test_moderator_bypasses_start_check(
        self,
        moderator_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Moderators can list challenges before the CTF starts."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, _ = moderator_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200

    async def test_user_allowed_when_hide_disabled(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Users can list challenges before start when hide setting is off."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "false"
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200

    async def test_user_allowed_when_no_start_time(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Users can list challenges when no start time is configured."""
        config_overrides["ctf.start_time"] = ""
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200


# ── submit ─────────────────────────────────────────────────────────────────────


class TestSubmitAfterEnd:
    async def test_user_blocked_when_ctf_ended(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Regular users cannot submit answers after the CTF ends."""
        config_overrides["ctf.end_time"] = PAST
        c, _ = user_client
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/submit",
            json={"answer": "flag"},
        )
        assert resp.status_code == 403

    async def test_admin_bypasses_end_check(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session,
        config_overrides: dict[str, str],
    ) -> None:
        """Admins can submit past the end time (timing guard is skipped, hits team check instead)."""
        config_overrides["ctf.end_time"] = PAST
        # Give the admin a team so it passes the team check and reaches the challenge lookup
        team = Team(id=UUID("00000000-0000-4000-9000-000000000001"), name="admin-team")
        db_session.add(team)
        c, admin_user = admin_client
        admin_user.team_id = team.id
        db_session.add(admin_user)
        await db_session.flush()

        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/submit",
            json={"answer": "flag"},
        )
        # 404 means the timing guard was bypassed and we reached the DB lookup
        assert resp.status_code == 404


class TestSubmitBeforeStart:
    async def test_user_blocked_when_ctf_not_started(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Regular users cannot submit answers before the CTF starts."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, _ = user_client
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/submit",
            json={"answer": "flag"},
        )
        assert resp.status_code == 403


# ── writeup visibility ──────────────────────────────────────────────────────────


class TestWriteupVisible:
    @pytest.mark.parametrize(
        ("challenge_completed", "release_after_end", "end_time", "expected"),
        [
            (True, "false", "", True),
            (False, "false", PAST, False),
            (False, "true", FUTURE, False),
            (False, "true", PAST, True),
        ],
        ids=["completed", "toggle_off", "event_not_ended", "toggle_on_and_ended"],
    )
    def test_writeup_visible(
        self,
        challenge_completed: bool,
        release_after_end: str,
        end_time: str,
        expected: bool,
    ) -> None:
        """Writeup shows once completed, or once the event ends if the toggle is on."""
        overrides = {
            "ctf.release_writeups_after_end": release_after_end,
            "ctf.end_time": end_time,
        }
        assert (
            _writeup_visible(
                challenge_completed=challenge_completed, overrides=overrides
            )
            is expected
        )


# ── hint unlock ────────────────────────────────────────────────────────────────


class TestHintUnlockAfterEnd:
    async def test_user_blocked_when_ctf_ended(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        """Regular users cannot unlock hints after the CTF ends."""
        config_overrides["ctf.end_time"] = PAST
        c, user = user_client
        # Without a team the request would 403 on the team guard instead.
        team = Team(name="ended_team")
        db_session.add(team)
        await db_session.flush()
        user.team_id = team.id
        await db_session.flush()

        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/hints/{NULL_UUID}/unlock"
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] != "SUB-403-TEAM"

    async def test_teamless_user_blocked(
        self,
        user_client: tuple[AsyncClient, User],
    ) -> None:
        """A hint is bought by a team, so a teamless user cannot unlock one."""
        c, _ = user_client
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/hints/{NULL_UUID}/unlock"
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-TEAM"


class TestHintUnlockSequentialLock:
    async def test_locked_question_hint_refused(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """A hint on a question locked behind an unsolved one stays locked."""
        c, user = user_client
        team = Team(name="seq_team")
        db_session.add(team)
        await db_session.flush()
        user.team_id = team.id

        challenge = StandardChallenge(title="Seq Test", is_active=True, sequential=True)
        db_session.add(challenge)
        await db_session.flush()
        first = Question(label="Q1", points=100, index=0, challenge_id=challenge.id)
        second = Question(label="Q2", points=100, index=1, challenge_id=challenge.id)
        db_session.add_all([first, second])
        await db_session.flush()
        hint = Hint(title="H", content="secret", cost=30, question_id=second.id)
        db_session.add(hint)
        await db_session.flush()

        resp = await c.post(
            f"/challenges/{challenge.id}/{second.id}/hints/{hint.id}/unlock"
        )

        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-SEQ"
        count = await db_session.scalar(
            select(func.count())
            .select_from(HintUnlock)
            .where(HintUnlock.team_id == team.id)
        )
        assert count == 0


class TestHintUnlockChargesOnce:
    async def test_second_unlock_is_free(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Re-unlocking returns the hint without charging the team twice."""
        c, user = user_client
        team = Team(name="unlock_team")
        db_session.add(team)
        await db_session.flush()
        user.team_id = team.id

        challenge = StandardChallenge(title="Unlock Test", is_active=True)
        db_session.add(challenge)
        await db_session.flush()
        question = Question(label="Q", points=100, challenge_id=challenge.id)
        db_session.add(question)
        await db_session.flush()
        hint = Hint(title="H", content="secret", cost=30, question_id=question.id)
        db_session.add(hint)
        await db_session.flush()

        url = f"/challenges/{challenge.id}/{question.id}/hints/{hint.id}/unlock"
        first = await c.post(url)
        second = await c.post(url)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["data"]["content"] == "secret"
        count = await db_session.scalar(
            select(func.count())
            .select_from(HintUnlock)
            .where(HintUnlock.team_id == team.id)
        )
        assert count == 1


# ── lifecycle hooks ────────────────────────────────────────────────────────────


async def _solvable(
    db_session: AsyncSession, user: User, flag: str
) -> tuple[StandardChallenge, Question]:
    """Create an active challenge with one question the flag solves."""
    await put_in_team(db_session, user)
    challenge = StandardChallenge(title="Hook Test", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    question = Question(label="Q", points=100, challenge_id=challenge.id)
    db_session.add(question)
    await db_session.flush()
    db_session.add(MatchSolution(value=flag, question_id=question.id))
    return challenge, question


class TestHookFailure:
    async def test_raising_hook_does_not_break_submit(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Hooks are best-effort: an override that raises still scores the flag."""
        flag = "NexCTF{hook_test}"
        c, user = user_client
        challenge, question = await _solvable(db_session, user, flag)

        async def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("plugin exploded")

        monkeypatch.setattr(StandardChallenge, "on_submit", _boom)
        monkeypatch.setattr(StandardChallenge, "on_solve", _boom)

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": flag}
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["is_correct"] is True

    async def test_hook_db_error_does_not_break_submit(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A hook that aborts the transaction must not cost the user the flag."""
        flag = "NexCTF{hook_sql}"
        c, user = user_client
        challenge, question = await _solvable(db_session, user, flag)

        async def _bad_sql(self: StandardChallenge, *_a: object, **_kw: object) -> None:
            session = async_object_session(self)
            assert session is not None
            await session.execute(text("SELECT 1 / 0"))

        monkeypatch.setattr(StandardChallenge, "on_submit", _bad_sql)

        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": flag}
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["is_correct"] is True


class TestInvalidConfigValues:
    """Unusable config values fail closed instead of opening or crashing."""

    @pytest.mark.parametrize(
        "key,path",
        [
            ("visibility.challenges", "/challenges"),
            ("visibility.scoreboard", "/scoreboard"),
        ],
    )
    async def test_unknown_visibility_is_refused(
        self,
        http_client: AsyncClient,
        config_overrides: dict[str, str],
        key: str,
        path: str,
    ) -> None:
        """A typo must not leave the surface at its (possibly public) default."""
        config_overrides[key] = "hiden"
        resp = await http_client.get(path)
        assert resp.status_code == 403

    async def test_malformed_start_time_does_not_500(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        config_overrides["ctf.start_time"] = "yesterday"
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200
