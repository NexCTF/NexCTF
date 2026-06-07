"""Tests for challenge endpoint event-timing guards."""

from __future__ import annotations

from uuid import UUID

import nexctf.core.appconfig as appconfig
import pytest
from httpx import AsyncClient

from nexctf.model import Team, User

NULL_UUID = "00000000-0000-0000-0000-000000000000"

FUTURE = "2099-01-01T00:00:00+00:00"
PAST = "2000-01-01T00:00:00+00:00"


# ── list challenges ────────────────────────────────────────────────────────────


class TestListChallengesBeforeStart:
    async def test_user_blocked_when_start_in_future(
        self,
        user_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regular users cannot list challenges before the CTF starts."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.start_time", FUTURE)
        monkeypatch.setitem(
            appconfig._CACHE, "ctf.hide_challenges_before_start", "true"
        )
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 403

    async def test_admin_bypasses_start_check(
        self,
        admin_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Admins can list challenges before the CTF starts."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.start_time", FUTURE)
        monkeypatch.setitem(
            appconfig._CACHE, "ctf.hide_challenges_before_start", "true"
        )
        c, _ = admin_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200

    async def test_moderator_bypasses_start_check(
        self,
        moderator_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Moderators can list challenges before the CTF starts."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.start_time", FUTURE)
        monkeypatch.setitem(
            appconfig._CACHE, "ctf.hide_challenges_before_start", "true"
        )
        c, _ = moderator_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200

    async def test_user_allowed_when_hide_disabled(
        self,
        user_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Users can list challenges before start when hide setting is off."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.start_time", FUTURE)
        monkeypatch.setitem(
            appconfig._CACHE, "ctf.hide_challenges_before_start", "false"
        )
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200

    async def test_user_allowed_when_no_start_time(
        self,
        user_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Users can list challenges when no start time is configured."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.start_time", "")
        monkeypatch.setitem(
            appconfig._CACHE, "ctf.hide_challenges_before_start", "true"
        )
        c, _ = user_client
        resp = await c.get("/challenges")
        assert resp.status_code == 200


# ── submit ─────────────────────────────────────────────────────────────────────


class TestSubmitAfterEnd:
    async def test_user_blocked_when_ctf_ended(
        self,
        user_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regular users cannot submit answers after the CTF ends."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.end_time", PAST)
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
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Admins can submit past the end time (timing guard is skipped, hits team check instead)."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.end_time", PAST)
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
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regular users cannot submit answers before the CTF starts."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.start_time", FUTURE)
        monkeypatch.setitem(
            appconfig._CACHE, "ctf.hide_challenges_before_start", "true"
        )
        c, _ = user_client
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/submit",
            json={"answer": "flag"},
        )
        assert resp.status_code == 403


# ── hint unlock ────────────────────────────────────────────────────────────────


class TestHintUnlockAfterEnd:
    async def test_user_blocked_when_ctf_ended(
        self,
        user_client: tuple[AsyncClient, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regular users cannot unlock hints after the CTF ends."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.end_time", PAST)
        c, _ = user_client
        resp = await c.post(
            f"/challenges/{NULL_UUID}/{NULL_UUID}/hints/{NULL_UUID}/unlock"
        )
        assert resp.status_code == 403
