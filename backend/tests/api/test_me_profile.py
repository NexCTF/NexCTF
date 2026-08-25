"""Tests for the self-service user and team profile endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import CustomFieldDefinition, CustomFieldValue, Team, User
from nexctf.model.custom_field import CustomFieldTarget, CustomFieldType
from tests.base import put_in_team


async def _definition(
    db_session: AsyncSession,
    target: CustomFieldTarget,
    field_type: CustomFieldType = CustomFieldType.string,
) -> CustomFieldDefinition:
    definition = CustomFieldDefinition(
        name=f"{target.value}_{field_type.value}",
        label="Field",
        field_type=field_type,
        target=target,
    )
    db_session.add(definition)
    await db_session.flush()
    return definition


class TestUserProfile:
    async def test_get_lists_every_user_definition(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        client, _ = user_client
        definition = await _definition(db_session, CustomFieldTarget.user)

        resp = await client.get("/me/profile")
        assert resp.status_code == 200
        fields = resp.json()["data"]["custom_fields"]
        assert [f["definition_id"] for f in fields] == [str(definition.id)]
        assert fields[0]["value"] is None

    async def test_update_writes_links_and_values(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        client, user = user_client
        definition = await _definition(db_session, CustomFieldTarget.user)

        resp = await client.put(
            "/me/profile",
            json={
                "links": [{"label": "blog", "url": "https://example.com"}],
                "custom_fields": {str(definition.id): "hello"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["custom_fields"][0]["value"] == "hello"
        assert user.links == [{"label": "blog", "url": "https://example.com"}]

    async def test_update_clears_a_value(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        client, user = user_client
        definition = await _definition(db_session, CustomFieldTarget.user)
        db_session.add(
            CustomFieldValue(
                definition_id=definition.id, user_id=user.id, value="stale"
            )
        )
        await db_session.flush()

        resp = await client.put(
            "/me/profile", json={"custom_fields": {str(definition.id): ""}}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["custom_fields"][0]["value"] is None

    async def test_update_clears_an_omitted_value(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """The payload is the whole set: an omitted definition is cleared."""
        client, user = user_client
        definition = await _definition(db_session, CustomFieldTarget.user)
        db_session.add(
            CustomFieldValue(
                definition_id=definition.id, user_id=user.id, value="stale"
            )
        )
        await db_session.flush()

        resp = await client.put("/me/profile", json={})
        assert resp.status_code == 200
        assert resp.json()["data"]["custom_fields"][0]["value"] is None

    async def test_update_locked(
        self,
        user_client: tuple[AsyncClient, User],
        config_overrides: dict[str, str],
    ) -> None:
        client, _ = user_client
        config_overrides["ctf.allow_user_customization"] = "false"

        resp = await client.put("/me/profile", json={})
        assert resp.status_code == 403

    async def test_rejects_a_team_definition(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """A user must not reach team fields by passing their definition id."""
        client, _ = user_client
        definition = await _definition(db_session, CustomFieldTarget.team)

        resp = await client.put(
            "/me/profile", json={"custom_fields": {str(definition.id): "x"}}
        )
        assert resp.status_code == 422

    async def test_rejects_a_non_http_link(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        client, _ = user_client

        resp = await client.put(
            "/me/profile",
            json={"links": [{"label": "xss", "url": "javascript:alert(1)"}]},
        )
        assert resp.status_code == 422

    async def test_rejects_a_mistyped_value(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        client, _ = user_client
        definition = await _definition(
            db_session, CustomFieldTarget.user, CustomFieldType.integer
        )

        resp = await client.put(
            "/me/profile", json={"custom_fields": {str(definition.id): "abc"}}
        )
        assert resp.status_code == 422


class TestTeamProfile:
    async def test_update_renames_the_team(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        client, user = user_client
        team = await put_in_team(db_session, user)
        definition = await _definition(db_session, CustomFieldTarget.team)

        resp = await client.put(
            "/me/team/profile",
            json={
                "name": "Renamed",
                "country": "FR",
                "custom_fields": {str(definition.id): "value"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == {
            "name": "Renamed",
            "country": "FR",
            "links": [],
            "custom_fields": [
                {
                    "definition_id": str(definition.id),
                    "label": "Field",
                    "field_type": "string",
                    "is_required": False,
                    "value": "value",
                }
            ],
        }
        assert team.name == "Renamed"

    async def test_rename_flushes_the_team_scoreboard_cache(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        mock_redis,
    ) -> None:
        client, user = user_client
        team = await put_in_team(db_session, user)

        await client.put("/me/team/profile", json={"name": "Renamed"})

        assert any(
            f"scoreboard:team:{team.id}" in call.args
            for call in mock_redis.delete.await_args_list
        )

    async def test_save_without_a_rename_leaves_the_cache_alone(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        mock_redis,
    ) -> None:
        """The route is player-reachable, so a no-op save must not flush."""
        client, user = user_client
        team = await put_in_team(db_session, user)

        await client.put("/me/team/profile", json={"name": team.name, "country": "FR"})

        mock_redis.delete.assert_not_awaited()

    async def test_locked_save_leaves_the_cache_alone(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
        mock_redis,
    ) -> None:
        client, user = user_client
        await put_in_team(db_session, user)
        config_overrides["ctf.allow_team_customization"] = "false"

        resp = await client.put("/me/team/profile", json={"name": "Renamed"})

        assert resp.status_code == 403
        mock_redis.delete.assert_not_awaited()

    async def test_update_rejects_a_taken_name(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """The unique index is the gate: the write runs in a savepoint that rolls
        back to a 409, leaving the surrounding transaction usable."""
        client, user = user_client
        team = await put_in_team(db_session, user)
        original = team.name
        db_session.add(Team(name="Taken", invite_code="TAKEN001"))
        await db_session.flush()

        resp = await client.put("/me/team/profile", json={"name": "Taken"})
        assert resp.status_code == 409

        await db_session.refresh(team)
        assert team.name == original

    async def test_update_locked(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
    ) -> None:
        client, user = user_client
        await put_in_team(db_session, user)
        config_overrides["ctf.allow_team_customization"] = "false"

        resp = await client.put("/me/team/profile", json={"name": "Renamed"})
        assert resp.status_code == 403

    async def test_update_without_a_team(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        client, _ = user_client

        resp = await client.put("/me/team/profile", json={"name": "Renamed"})
        assert resp.status_code == 409
