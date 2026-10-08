"""Tests for user-agent sightings and the clients they are reported as."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi_multiauth import hash_token
from sqlalchemy import select

from nexctf.api.security import create_api_token
from nexctf.enums import ClientCategory, ClientSource
from nexctf.model import Event, User, UserAgentSighting, UserToken
from nexctf.module.client import (
    AI_PATTERNS_KEY,
    SEEN_KEY_PREFIX,
    SIGHTING_THROTTLE,
    ClientInfo,
    category_expression,
)

from ..base import (
    NULL_UUID,
    ListGuardMixin,
    get_data,
    make_solvable,
    make_team,
    make_user,
    put_in_team,
)

CLIENTS = "/admin/session/clients"
SUMMARY = f"{CLIENTS}/summary"
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) Chrome/141.0 Safari/537.36"
AI_UA = "Mozilla/5.0 AppleWebKit/537.36 (compatible; Claude-User/1.0)"
CURL_UA = "curl/8.10.1"


async def _sightings(db_session, user: User) -> list[UserAgentSighting]:
    return list(
        (
            await db_session.scalars(
                select(UserAgentSighting).where(UserAgentSighting.user_id == user.id)
            )
        ).all()
    )


async def _add_sighting(
    db_session,
    user: User,
    user_agent: str,
    *,
    source: ClientSource = ClientSource.cookie,
    token: UserToken | None = None,
    hours_ago: float = 0,
) -> UserAgentSighting:
    seen = datetime.now(UTC) - timedelta(hours=hours_ago)
    row = UserAgentSighting(
        user_id=user.id,
        team_id=user.team_id,
        token_id=token.id if token else None,
        user_agent=user_agent,
        ua_hash=hash_token(user_agent),
        source=ClientSource.token if token else source,
        first_seen_at=seen,
        last_seen_at=seen,
    )
    db_session.add(row)
    await db_session.flush()
    return row


@pytest.fixture
def no_recording(monkeypatch):
    """Keep the test clients' own requests out of the sightings."""
    monkeypatch.setattr("nexctf.api.dep.record_sighting", AsyncMock())


async def _rows(admin_client, query: str = "") -> list[dict]:
    c, _ = admin_client
    return await get_data(c, f"{CLIENTS}{query}")


async def _category_of(
    db_session, row: UserAgentSighting, overrides: dict[str, str] | None = None
) -> ClientCategory:
    expr = category_expression(overrides or {})
    value = await db_session.scalar(select(expr).where(UserAgentSighting.id == row.id))
    return ClientCategory(value)


class TestCategoryExpression:
    @pytest.mark.parametrize(
        ("user_agent", "expected"),
        [
            (AI_UA, ClientCategory.AI),
            ("Mozilla/5.0 (compatible; GPTBot/1.2)", ClientCategory.AI),
            (CURL_UA, ClientCategory.AUTOMATION),
            ("python-httpx/0.28.1", ClientCategory.AUTOMATION),
            ("PYTHON-REQUESTS/2.32", ClientCategory.AUTOMATION),
            ("", ClientCategory.AUTOMATION),
            (BROWSER_UA, ClientCategory.BROWSER),
        ],
    )
    async def test_default_patterns(
        self, db_session, user_agent: str, expected: ClientCategory
    ):
        user = await make_user(db_session, "classified")
        row = await _add_sighting(db_session, user, user_agent)
        assert await _category_of(db_session, row) is expected

    async def test_ai_wins_over_automation(self, db_session):
        """A headless browser driven by an agent is reported as AI."""
        user = await make_user(db_session, "headless")
        row = await _add_sighting(
            db_session, user, "HeadlessChrome/141.0 ChatGPT-User/1.0"
        )
        assert await _category_of(db_session, row) is ClientCategory.AI

    async def test_patterns_come_from_config(self, db_session):
        user = await make_user(db_session, "custom")
        mine = await _add_sighting(db_session, user, "My-Agent/2.0")
        claude = await _add_sighting(db_session, user, AI_UA)
        overrides = {AI_PATTERNS_KEY: "my-agent\n\n  "}

        assert await _category_of(db_session, mine, overrides) is ClientCategory.AI
        assert (
            await _category_of(db_session, claude, overrides) is ClientCategory.BROWSER
        )

    async def test_wildcards_in_patterns_are_literal(self, db_session):
        user = await make_user(db_session, "wild")
        row = await _add_sighting(db_session, user, "tool_x/1.0")
        overrides = {AI_PATTERNS_KEY: "tool%x"}

        assert await _category_of(db_session, row, overrides) is ClientCategory.BROWSER


class TestClientInfo:
    def test_truncates_and_defaults_the_header(self):
        assert ClientInfo.build(None, None).user_agent == ""
        assert len(ClientInfo.build("x" * 1000, None).user_agent) == 512

    def test_token_id_makes_it_a_token_client(self):
        info = ClientInfo.build(CURL_UA, UUID(NULL_UUID))
        assert info.source is ClientSource.token
        assert info.event_meta() == {"user_agent": CURL_UA, "source": "token"}


class TestRecordSighting:
    async def test_cookie_request_is_recorded(self, user_client, db_session):
        c, user = user_client
        team = await put_in_team(db_session, user)

        await c.get("/me/profile", headers={"User-Agent": BROWSER_UA})

        [row] = await _sightings(db_session, user)
        assert row.user_agent == BROWSER_UA
        assert row.source is ClientSource.cookie
        assert row.token_id is None
        assert row.team_id == team.id

    async def test_token_request_records_the_token(
        self, client_factory, db_session, override_db_context
    ):
        user = await make_user(db_session, "scripted")
        raw, token = await create_api_token(user.id, scopes=["read:profile"])
        async with client_factory() as c:
            c.headers["Authorization"] = f"Bearer {raw}"
            await c.get("/me/profile", headers={"User-Agent": CURL_UA})

        [row] = await _sightings(db_session, user)
        assert row.source is ClientSource.token
        assert row.token_id == token.id

    async def test_optional_auth_routes_record_too(self, user_client, db_session):
        c, user = user_client

        await c.get("/challenges", headers={"User-Agent": AI_UA})

        assert [r.user_agent for r in await _sightings(db_session, user)] == [AI_UA]

    async def test_a_missing_header_is_recorded_empty(self, user_client, db_session):
        c, user = user_client
        del c.headers["User-Agent"]

        await c.get("/me/profile")

        assert [r.user_agent for r in await _sightings(db_session, user)] == [""]

    async def test_throttled_by_a_redis_key(self, user_client, db_session, mock_redis):
        c, user = user_client
        mock_redis.set = AsyncMock(return_value=None)

        await c.get("/me/profile", headers={"User-Agent": BROWSER_UA})

        assert await _sightings(db_session, user) == []
        key = f"{SEEN_KEY_PREFIX}{user.id}:cookie:{hash_token(BROWSER_UA)}"
        mock_redis.set.assert_awaited_once_with(key, "1", nx=True, ex=SIGHTING_THROTTLE)

    async def test_seen_again_moves_last_seen_only(self, user_client, db_session):
        c, user = user_client
        old = await _add_sighting(db_session, user, BROWSER_UA, hours_ago=3)
        first_seen = old.first_seen_at

        await c.get("/me/profile", headers={"User-Agent": BROWSER_UA})

        [row] = await _sightings(db_session, user)
        await db_session.refresh(row)
        assert row.first_seen_at == first_seen
        assert row.last_seen_at > first_seen

    async def test_submission_events_carry_the_client(self, user_client, db_session):
        c, user = user_client
        challenge, question = await make_solvable(db_session, user, "flag")

        await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": "nope"},
            headers={"User-Agent": CURL_UA},
        )

        event = await db_session.scalar(
            select(Event).where(Event.event_type == "submission.wrong")
        )
        assert event is not None
        assert event.meta["user_agent"] == CURL_UA
        assert event.meta["source"] == "cookie"

    async def test_recorded_once_when_both_auth_paths_run(
        self, user_client, db_session, mock_redis
    ):
        """Submitting resolves the required and the optional user dependency."""
        c, user = user_client
        challenge, question = await make_solvable(db_session, user, "flag")

        await c.post(
            f"/challenges/{challenge.id}/{question.id}/submit",
            json={"answer": "nope"},
        )

        seen = [
            call
            for call in mock_redis.set.await_args_list
            if str(call.args[0]).startswith(SEEN_KEY_PREFIX)
        ]
        assert len(seen) == 1


@pytest.mark.usefixtures("no_recording")
class TestListClients(ListGuardMixin):
    PREFIX = CLIENTS

    async def test_one_row_per_account_and_user_agent(self, admin_client, db_session):
        alice = await make_user(db_session, "alice")
        bob = await make_user(db_session, "bob")
        team = await put_in_team(db_session, alice)
        _, token = await create_api_token(bob.id, scopes=[], name="solver")
        await _add_sighting(db_session, alice, AI_UA)
        await _add_sighting(db_session, bob, AI_UA, token=token)

        rows = {r["username"]: r for r in await _rows(admin_client)}

        assert rows["alice"]["category"] == "ai"
        assert rows["alice"]["team_name"] == team.name
        assert rows["alice"]["source"] == "cookie"
        assert rows["bob"]["token_name"] == "solver"
        assert rows["bob"]["team_id"] is None

    async def test_most_recently_seen_first(self, admin_client, db_session):
        user = await make_user(db_session, "ordered")
        await _add_sighting(db_session, user, BROWSER_UA, hours_ago=2)
        await _add_sighting(db_session, user, CURL_UA)

        assert [r["user_agent"] for r in await _rows(admin_client)] == [
            CURL_UA,
            BROWSER_UA,
        ]

    async def test_filters_on_category(self, admin_client, db_session):
        user = await make_user(db_session, "mixed")
        for ua in (BROWSER_UA, CURL_UA, AI_UA):
            await _add_sighting(db_session, user, ua)

        rows = await _rows(admin_client, "?category=ai&category=automation")

        assert {r["user_agent"] for r in rows} == {AI_UA, CURL_UA}

    async def test_filters_on_source(self, admin_client, db_session):
        user = await make_user(db_session, "sourced")
        await _add_sighting(db_session, user, BROWSER_UA)
        await _add_sighting(db_session, user, CURL_UA, source=ClientSource.token)

        rows = await _rows(admin_client, "?source=token")

        assert [r["user_agent"] for r in rows] == [CURL_UA]

    async def test_searches_username_and_user_agent(self, admin_client, db_session):
        alice = await make_user(db_session, "alice")
        bob = await make_user(db_session, "bob")
        await _add_sighting(db_session, alice, BROWSER_UA)
        await _add_sighting(db_session, bob, CURL_UA)

        assert [r["username"] for r in await _rows(admin_client, "?search=alice")] == [
            "alice"
        ]
        assert [r["username"] for r in await _rows(admin_client, "?search=curl")] == [
            "bob"
        ]

    async def test_offers_category_first_among_filters(self, admin_client, db_session):
        user = await make_user(db_session, "faceted")
        await _add_sighting(db_session, user, BROWSER_UA)

        c, _ = admin_client
        resp = await c.get(CLIENTS)

        facets = resp.json()["filter_attributes"]
        assert next(iter(facets)) == "category"
        assert facets["category"] == ["ai", "automation", "browser"]
        assert facets["source"] == ["cookie"]
        assert facets["team__name"] == []

    async def test_window_filters_on_last_seen(self, admin_client, db_session):
        user = await make_user(db_session, "stale")
        await _add_sighting(db_session, user, CURL_UA, hours_ago=48)

        assert await _rows(admin_client, "?window=day") == []
        assert await _rows(admin_client, "?window=live") == []
        assert [r["user_agent"] for r in await _rows(admin_client, "?window=all")] == [
            CURL_UA
        ]

    async def test_team_is_the_one_at_sighting_time(self, admin_client, db_session):
        user = await make_user(db_session, "mover")
        team = await put_in_team(db_session, user)
        await _add_sighting(db_session, user, AI_UA)
        user.team_id = (await make_team(db_session, "elsewhere")).id
        await db_session.flush()

        [row] = await _rows(admin_client)

        assert row["team_id"] == str(team.id)


@pytest.mark.usefixtures("no_recording")
class TestClientsSummary(ListGuardMixin):
    PREFIX = SUMMARY

    async def test_counts_clients_and_accounts_per_kind(self, admin_client, db_session):
        c, _ = admin_client
        alice = await make_user(db_session, "alice")
        bob = await make_user(db_session, "bob")
        await _add_sighting(db_session, alice, AI_UA)
        await _add_sighting(db_session, alice, BROWSER_UA)
        await _add_sighting(db_session, bob, AI_UA, source=ClientSource.token)
        await _add_sighting(db_session, bob, CURL_UA, hours_ago=48)

        day = await get_data(c, SUMMARY)
        whole = await get_data(c, f"{SUMMARY}?window=all")

        assert day == {
            "client_count": 2,
            "account_count": 2,
            "ai_account_count": 2,
            "automation_account_count": 0,
            "token_account_count": 1,
        }
        assert whole["client_count"] == 3
        assert whole["automation_account_count"] == 1


class TestListUserClients(ListGuardMixin):
    PREFIX = f"/admin/user/{NULL_UUID}/clients"

    async def test_lists_one_users_clients_with_token_name(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        user = await make_user(db_session, "carol")
        _, token = await create_api_token(user.id, scopes=[], name="solver")
        await _add_sighting(db_session, user, CURL_UA, token=token)
        await _add_sighting(db_session, user, BROWSER_UA, hours_ago=1)

        data = await get_data(c, f"/admin/user/{user.id}/clients")

        assert [r["user_agent"] for r in data] == [CURL_UA, BROWSER_UA]
        assert data[0]["category"] == "automation"
        assert data[0]["token_name"] == "solver"
        assert data[1]["category"] == "browser"
