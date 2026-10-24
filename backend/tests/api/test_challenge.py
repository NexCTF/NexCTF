"""Tests for challenge endpoint event-timing guards."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_object_session

from nexctf.api.routes.challenge import _writeup_visible
from nexctf.model import HintUnlock, Team, User
from nexctf.model.question import Hint, Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.mcq.model import MCQSolution
from tests.base import FUTURE, NULL_UUID, PAST, make_solvable, put_in_team

# ── list challenges ────────────────────────────────────────────────────────────


class TestListChallengesBeforeStart:
    async def test_user_blocked_when_start_in_future(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        """Users cannot list challenges before the CTF starts."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 403

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
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        """Users cannot submit answers after the CTF ends."""
        config_overrides["ctf.end_time"] = PAST
        c, user = user_client
        await put_in_team(db_session, user)
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/submit",
            json={"answer": "flag"},
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "CTF-403-ENDED"


class TestSubmitBody:
    async def test_oversized_answer_is_refused(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, user = user_client
        challenge, question = await make_solvable(db_session, user, "flag")
        resp = await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": "a" * 20_000},
        )
        assert resp.status_code == 422


class TestSubmitBeforeStart:
    async def test_user_blocked_when_ctf_not_started(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        """Users cannot submit answers before the CTF starts."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "true"
        c, user = user_client
        await put_in_team(db_session, user)
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/submit",
            json={"answer": "flag"},
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "CTF-403-NOT-STARTED"

    @pytest.mark.parametrize("path", ["submit", "hints/" + NULL_UUID + "/unlock"])
    async def test_blocked_while_challenges_are_previewable(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
        path: str,
    ) -> None:
        """Showing challenges before the start must not open submissions."""
        config_overrides["ctf.start_time"] = FUTURE
        config_overrides["ctf.hide_challenges_before_start"] = "false"
        c, user = user_client
        await put_in_team(db_session, user)
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/{path}", json={"answer": "flag"}
        )
        assert resp.json()["error_code"] == "CTF-403-NOT-STARTED"


class TestSubmitRateLimitKey:
    async def test_limit_is_keyed_on_the_team(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        mock_redis,
    ) -> None:
        """Flag brute-force is team-level, so the window must be shared per team."""
        c, user = user_client
        team = await put_in_team(db_session, user)

        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/submit",
            json={"answer": "flag"},
        )
        assert resp.status_code == 404

        key = mock_redis.pipeline.return_value.zadd.call_args[0][0]
        assert key == f"rl:submit:{team.id}"


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
        """Users cannot unlock hints after the CTF ends."""
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
        assert resp.json()["error_code"] == "CTF-403-ENDED"

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


async def _sequential(
    db_session: AsyncSession, **second: object
) -> tuple[StandardChallenge, Question, Question]:
    """An active sequential challenge with Q1 then Q2 (Q2 takes *second*)."""
    challenge = StandardChallenge(title="Seq Test", is_active=True, sequential=True)
    db_session.add(challenge)
    await db_session.flush()
    first = Question(label="Q1", points=100, index=0, challenge_id=challenge.id)
    later = Question(
        label="Q2", points=100, challenge_id=challenge.id, **{"index": 1, **second}
    )
    db_session.add_all([first, later])
    await db_session.flush()
    return challenge, first, later


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
        challenge, _, second = await _sequential(db_session)
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


class TestSequentialTiedIndexes:
    async def test_the_question_shown_locked_refuses_answers(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Questions sharing an index still unlock one after the other."""
        c, user = user_client
        await put_in_team(db_session, user)
        challenge, _, _ = await _sequential(db_session, index=0)

        detail = (await c.get(f"/challenges/{challenge.id}")).json()["data"]
        locked = next(q for q in detail["questions"] if q["is_locked"])
        resp = await c.post(
            f"/challenges/{challenge.id}/{locked['id']}/submit", json={"answer": "x"}
        )
        assert resp.json()["error_code"] == "SUB-403-SEQ"


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
        challenge, question = await make_solvable(db_session, user, flag)

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
        challenge, question = await make_solvable(db_session, user, flag)

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


# ── sequential lock ────────────────────────────────────────────────────────────


class TestSequentialLock:
    async def test_locked_question_hides_its_statement(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, user = user_client
        await put_in_team(db_session, user)
        challenge, _, _ = await _sequential(
            db_session, description="Look in /etc/secret", tags=["pivot"]
        )

        resp = await c.get(f"/challenges/{challenge.id}")
        locked = resp.json()["data"]["questions"][1]
        assert locked["is_locked"] is True
        assert locked["description"] is None
        assert locked["tags"] == []


# ── option order ───────────────────────────────────────────────────────────────


class TestOptionOrder:
    async def test_options_keep_their_order_across_reloads(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, user = user_client
        challenge, question = await make_solvable(db_session, user, "a")
        choices = [f"option {n}" for n in range(8)]
        db_session.add(
            MCQSolution(
                question_id=question.id,
                correct_answers=choices[:1],
                other_options=choices[1:],
            )
        )
        await db_session.flush()

        def options(resp) -> list[str]:
            return resp.json()["data"]["questions"][0]["options"]

        first = options(await c.get(f"/challenges/{challenge.id}"))
        second = options(await c.get(f"/challenges/{challenge.id}"))
        assert sorted(first) == choices
        assert first == second
