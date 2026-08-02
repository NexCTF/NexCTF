"""Tests for the shared request dependencies in nexctf.api.dep."""

from httpx import AsyncClient

from nexctf.model import User


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
