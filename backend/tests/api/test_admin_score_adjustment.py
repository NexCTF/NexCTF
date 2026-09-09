"""The challenge tied to a score adjustment can be set, changed and cleared."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import Team, User
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge

PREFIX = "/admin/score-adjustment"


async def _setup(db_session: AsyncSession) -> tuple[Team, StandardChallenge]:
    team = Team(name="adj_admin_team")
    challenge = StandardChallenge(title="Adjustable", is_active=True)
    db_session.add_all([team, challenge])
    await db_session.flush()
    return team, challenge


class TestScoreAdjustmentChallenge:
    async def test_create_with_challenge(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        c, _ = admin_client
        team, challenge = await _setup(db_session)

        resp = await c.post(
            PREFIX,
            json={
                "team_id": str(team.id),
                "amount": 25,
                "reason": "Clean writeup",
                "challenge_id": str(challenge.id),
            },
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["challenge_id"] == str(challenge.id)

    async def test_update_sets_then_clears_the_challenge(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """An operator who picked the wrong challenge must be able to correct it."""
        c, _ = admin_client
        team, challenge = await _setup(db_session)
        created = await c.post(
            PREFIX,
            json={"team_id": str(team.id), "amount": 25, "reason": "Clean writeup"},
        )
        adj_id = created.json()["data"]["id"]

        resp = await c.put(
            f"{PREFIX}/{adj_id}", json={"id": adj_id, "challenge_id": str(challenge.id)}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["challenge_id"] == str(challenge.id)

        resp = await c.put(
            f"{PREFIX}/{adj_id}", json={"id": adj_id, "challenge_id": None}
        )
        assert resp.json()["data"]["challenge_id"] is None

    async def test_update_without_the_key_preserves_the_challenge(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Omitting challenge_id must not silently unlink the challenge."""
        c, _ = admin_client
        team, challenge = await _setup(db_session)
        created = await c.post(
            PREFIX,
            json={
                "team_id": str(team.id),
                "amount": 25,
                "reason": "Clean writeup",
                "challenge_id": str(challenge.id),
            },
        )
        adj_id = created.json()["data"]["id"]

        resp = await c.put(f"{PREFIX}/{adj_id}", json={"id": adj_id, "amount": 30})

        assert resp.json()["data"]["challenge_id"] == str(challenge.id)
