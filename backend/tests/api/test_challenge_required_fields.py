"""Required custom fields must be filled before a player can submit."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import User
from nexctf.model.custom_field import (
    CustomFieldDefinition,
    CustomFieldTarget,
    CustomFieldValue,
)
from tests.base import make_solvable, make_user

_ALLOW = {
    CustomFieldTarget.user: "ctf.allow_user_customization",
    CustomFieldTarget.team: "ctf.allow_team_customization",
}


async def _required(
    db_session: AsyncSession, target: CustomFieldTarget, **extra: bool
) -> CustomFieldDefinition:
    definition = CustomFieldDefinition(
        name=f"required_{target.value}",
        label="Field",
        target=target,
        is_required=True,
        **extra,
    )
    db_session.add(definition)
    await db_session.flush()
    return definition


async def _fill(
    db_session: AsyncSession, definition: CustomFieldDefinition, user: User, value: str
) -> None:
    owner = (
        {"user_id": user.id}
        if definition.target is CustomFieldTarget.user
        else {"team_id": user.team_id}
    )
    db_session.add(CustomFieldValue(definition_id=definition.id, value=value, **owner))
    await db_session.flush()


async def _submit(client: AsyncClient, challenge, question):
    return await client.post(
        f"/challenges/{challenge.id}/{question.id}/submit", json={"answer": "flag"}
    )


@pytest.mark.parametrize("target", list(CustomFieldTarget))
class TestRequiredFields:
    async def test_submit_refused_until_filled(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
        target: CustomFieldTarget,
    ) -> None:
        client, user = user_client
        challenge, question = await make_solvable(db_session, user, "flag")
        definition = await _required(db_session, target)
        config_overrides[_ALLOW[target]] = "true"

        resp = await _submit(client, challenge, question)
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "SUB-403-PROFILE"

        await _fill(db_session, definition, user, "value")
        resp = await _submit(client, challenge, question)
        assert resp.json()["data"]["is_correct"] is True

    async def test_blank_value_does_not_count(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
        target: CustomFieldTarget,
    ) -> None:
        client, user = user_client
        challenge, question = await make_solvable(db_session, user, "flag")
        definition = await _required(db_session, target)
        await _fill(db_session, definition, user, "  ")
        config_overrides[_ALLOW[target]] = "true"

        resp = await _submit(client, challenge, question)
        assert resp.json()["error_code"] == "SUB-403-PROFILE"

    async def test_field_the_player_cannot_edit_is_not_enforced(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
        target: CustomFieldTarget,
    ) -> None:
        client, user = user_client
        challenge, question = await make_solvable(db_session, user, "flag")
        await _required(db_session, target, is_self_editable=False)
        config_overrides[_ALLOW[target]] = "true"

        resp = await _submit(client, challenge, question)
        assert resp.json()["data"]["is_correct"] is True

    async def test_not_enforced_while_customization_is_off(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        config_overrides: dict[str, str],
        target: CustomFieldTarget,
    ) -> None:
        client, user = user_client
        challenge, question = await make_solvable(db_session, user, "flag")
        await _required(db_session, target)
        config_overrides[_ALLOW[target]] = "false"

        resp = await _submit(client, challenge, question)
        assert resp.json()["data"]["is_correct"] is True


async def test_another_owner_value_does_not_count(
    user_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
    config_overrides: dict[str, str],
) -> None:
    client, user = user_client
    challenge, question = await make_solvable(db_session, user, "flag")
    definition = await _required(db_session, CustomFieldTarget.user)
    other = await make_user(db_session, "other_owner")
    await _fill(db_session, definition, other, "value")
    config_overrides["ctf.allow_user_customization"] = "true"

    resp = await _submit(client, challenge, question)
    assert resp.json()["error_code"] == "SUB-403-PROFILE"
