"""Admin lifecycle hooks: called once per write, inside the write's transaction."""

from uuid import UUID

import pytest
from fastapi_toolsets.exceptions import ApiException
from fastapi_toolsets.schemas import ApiError
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Challenge, User
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.schema.challenge import AdminChallengeCreate, AdminChallengeUpdate

from ..hooks import HookRecorder

PREFIX = "/admin/challenge"


class UpstreamRejectedError(ApiException):
    api_error = ApiError(
        code=502,
        msg="Upstream rejected the challenge",
        desc="The external service refused the scenario.",
        err_code="TEST-502",
    )


async def _count(session: AsyncSession) -> int:
    return (
        await session.execute(select(func.count()).select_from(Challenge))
    ).scalar_one()


@pytest.fixture
async def challenge(db_session: AsyncSession) -> StandardChallenge:
    challenge = StandardChallenge(title="Existing", category="web")
    db_session.add(challenge)
    await db_session.flush()
    return challenge


class TestHooksAreCalled:
    async def test_create_calls_after_create_with_the_create_schema(
        self, admin_client: tuple[AsyncClient, User], hooks: HookRecorder
    ) -> None:
        c, _ = admin_client
        resp = await c.post(f"{PREFIX}/standard", json={"title": "Fresh"})

        assert resp.status_code == 200
        [call] = hooks.calls
        assert call.name == "after_create"
        assert call.challenge_id == UUID(resp.json()["data"]["id"])
        assert isinstance(call.obj, AdminChallengeCreate)
        assert call.obj.title == "Fresh"

    async def test_update_calls_after_update_with_the_changed_columns(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        challenge: StandardChallenge,
    ) -> None:
        c, _ = admin_client
        resp = await c.put(
            f"{PREFIX}/{challenge.id}",
            json={"id": str(challenge.id), "title": "Renamed"},
        )

        assert resp.status_code == 200
        [call] = hooks.calls
        assert call.name == "after_update"
        assert call.challenge_id == challenge.id
        assert isinstance(call.obj, AdminChallengeUpdate)
        assert call.changed == {"title"}

    async def test_an_unchanged_update_reports_no_changed_column(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        challenge: StandardChallenge,
    ) -> None:
        c, _ = admin_client
        resp = await c.put(
            f"{PREFIX}/{challenge.id}",
            json={"id": str(challenge.id), "title": "Existing"},
        )

        assert resp.status_code == 200
        [call] = hooks.calls
        assert call.changed == set()

    async def test_delete_calls_before_delete(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        challenge: StandardChallenge,
    ) -> None:
        c, _ = admin_client
        resp = await c.delete(f"{PREFIX}/{challenge.id}")

        assert resp.status_code == 200
        [call] = hooks.calls
        assert call.name == "before_delete"
        assert call.challenge_id == challenge.id


class TestRaisingHookRollsBack:
    async def test_create_leaves_no_row_and_answers_the_plugin_error(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        db_session: AsyncSession,
    ) -> None:
        c, _ = admin_client
        hooks.raise_with = UpstreamRejectedError()

        resp = await c.post(f"{PREFIX}/standard", json={"title": "Doomed"})

        body = resp.json()
        assert resp.status_code == 502
        assert body["error_code"] == "TEST-502"
        assert body["message"] == "Upstream rejected the challenge"
        assert await _count(db_session) == 0

    async def test_update_is_not_applied(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        db_session: AsyncSession,
        challenge: StandardChallenge,
    ) -> None:
        c, _ = admin_client
        hooks.raise_with = UpstreamRejectedError()

        resp = await c.put(
            f"{PREFIX}/{challenge.id}",
            json={"id": str(challenge.id), "title": "Renamed"},
        )

        assert resp.status_code == 502
        await db_session.refresh(challenge)
        assert challenge.title == "Existing"

    async def test_delete_keeps_the_row(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        db_session: AsyncSession,
        challenge: StandardChallenge,
    ) -> None:
        c, _ = admin_client
        hooks.raise_with = UpstreamRejectedError()

        resp = await c.delete(f"{PREFIX}/{challenge.id}")

        assert resp.status_code == 502
        assert await _count(db_session) == 1

    async def test_any_other_exception_rolls_back(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        db_session: AsyncSession,
    ) -> None:
        """The test transport re-raises what the app's 500 handler answers."""
        c, _ = admin_client
        hooks.raise_with = RuntimeError("plugin exploded")

        with pytest.raises(RuntimeError, match="plugin exploded"):
            await c.post(f"{PREFIX}/standard", json={"title": "Doomed"})

        assert await _count(db_session) == 0

    async def test_a_duplicate_title_is_still_a_409(
        self,
        admin_client: tuple[AsyncClient, User],
        hooks: HookRecorder,
        challenge: StandardChallenge,
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            f"{PREFIX}/standard", json={"id": str(challenge.id), "title": "Existing"}
        )

        assert resp.status_code == 409
        assert hooks.calls == []
