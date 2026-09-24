"""Tests for the shared request dependencies in nexctf.api.dep."""

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import User
from nexctf.model.question import Question
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution


class TestConfigDep:
    """A request resolves the config snapshot exactly once."""

    async def test_read_path_takes_one_snapshot(
        self,
        user_client: tuple[AsyncClient, User],
        mock_redis,
    ) -> None:
        """The event dependency and the handler body share one read."""
        c, _ = user_client
        mock_redis.hgetall.reset_mock()
        resp = await c.get("/challenges")
        assert resp.status_code == 200
        assert mock_redis.hgetall.call_count == 1

    async def test_login_takes_one_snapshot(
        self,
        http_client: AsyncClient,
        mock_redis,
    ) -> None:
        """Login reads config for the captcha and the rate limit, but fetches once."""
        mock_redis.hgetall.reset_mock()
        await http_client.post(
            "/auth/token", data={"username": "nobody", "password": "nope"}
        )
        assert mock_redis.hgetall.call_count == 1

    async def test_register_takes_one_snapshot(
        self,
        http_client: AsyncClient,
        mock_redis,
    ) -> None:
        """Register reads the registration gate, the captcha and email.enabled."""
        mock_redis.hgetall.reset_mock()
        await http_client.post(
            "/auth/register",
            json={"username": "snapshotuser", "password": "strongpass"},
        )
        assert mock_redis.hgetall.call_count == 1


def _fields(resp: Response) -> list[str]:
    """Return the fields named by a 422 validation response."""
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "VAL-422"
    return [error["field"] for error in body["data"]["errors"]]


async def _question(db_session: AsyncSession) -> Question:
    """Create a challenge with one question."""
    challenge = StandardChallenge(title="Typed body", description="d")
    db_session.add(challenge)
    await db_session.flush()
    question = Question(label="Q", points=100, challenge_id=challenge.id)
    db_session.add(question)
    await db_session.flush()
    return question


class TestTypedBodyValidation:
    """Typed challenge and solution bodies answer 422, never 500."""

    async def test_challenge_create(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post("/admin/challenge/standard", json={"description": "d"})
        assert _fields(resp) == ["title"]

    async def test_challenge_update(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        question = await _question(db_session)
        uuid = question.challenge_id
        resp = await c.put(
            f"/admin/challenge/{uuid}", json={"id": str(uuid), "is_active": "nope"}
        )
        assert _fields(resp) == ["is_active"]

    async def test_solution_create(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        question = await _question(db_session)
        resp = await c.post(
            "/admin/solution/regex",
            json={"question_id": str(question.id), "pattern": "x", "flags": ["Z"]},
        )
        assert _fields(resp) == ["flags"]

    async def test_solution_update(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        question = await _question(db_session)
        solution = MatchSolution(value="flag", question_id=question.id)
        db_session.add(solution)
        await db_session.flush()
        resp = await c.put(
            f"/admin/solution/{solution.id}",
            json={"id": str(solution.id), "value": 123},
        )
        assert _fields(resp) == ["value"]

    async def test_malformed_json(self, admin_client: tuple[AsyncClient, User]) -> None:
        c, _ = admin_client
        resp = await c.post(
            "/admin/challenge/standard",
            content=b"{nope",
            headers={"Content-Type": "application/json"},
        )
        assert _fields(resp) == ["1"]
