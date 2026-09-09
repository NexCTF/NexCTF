"""A challenge detail carries the team's adjustments tied to that challenge."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import ScoreAdjustment, Team, User
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from tests.base import put_in_team


async def _setup(
    db_session: AsyncSession, user: User
) -> tuple[StandardChallenge, StandardChallenge, Team]:
    """Give *user* a team and two active challenges."""
    team = await put_in_team(db_session, user)
    challenges = [
        StandardChallenge(title=title, is_active=True)
        for title in ("Adjusted", "Untouched")
    ]
    db_session.add_all(challenges)
    await db_session.flush()
    return challenges[0], challenges[1], team


class TestChallengeScoreAdjustments:
    async def test_only_this_challenge_and_this_team(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """Adjustments of another team, or with no challenge, must not leak in."""
        c, user = user_client
        adjusted, untouched, team = await _setup(db_session, user)
        other = Team(name="adj_other_team")
        db_session.add(other)
        await db_session.flush()
        mine = ScoreAdjustment(
            amount=25,
            reason="Clean writeup",
            team_id=team.id,
            challenge_id=adjusted.id,
            created_by_id=user.id,
        )
        db_session.add_all(
            [
                mine,
                ScoreAdjustment(
                    amount=-10,
                    reason="Other team penalty",
                    team_id=other.id,
                    challenge_id=adjusted.id,
                    created_by_id=user.id,
                ),
                ScoreAdjustment(
                    amount=5,
                    reason="Unrelated bonus",
                    team_id=team.id,
                    created_by_id=user.id,
                ),
            ]
        )
        await db_session.flush()

        resp = await c.get(f"/challenges/{adjusted.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["score_adjustments"] == [
            {"id": str(mine.id), "amount": 25, "reason": "Clean writeup"}
        ]

        resp = await c.get(f"/challenges/{untouched.id}")
        assert resp.json()["data"]["score_adjustments"] == []

    async def test_teamless_user_gets_none(
        self,
        user_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
    ) -> None:
        """A user with no team has no adjustments to show."""
        c, user = user_client
        adjusted, _, _ = await _setup(db_session, user)
        user.team_id = None
        await db_session.flush()

        resp = await c.get(f"/challenges/{adjusted.id}")
        assert resp.json()["data"]["score_adjustments"] == []
