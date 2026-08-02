"""Tests for the config store's Redis mirror."""

from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.core import appconfig
from nexctf.model.config import ConfigEntry


class TestSyncToRedis:
    """The mirror writes stored database values into Redis."""

    async def test_restores_keys_missing_from_redis(
        self,
        db_session: AsyncSession,
        mock_redis,
    ) -> None:
        db_session.add(ConfigEntry(key="ctf.team_size", value="7"))
        await db_session.flush()
        mock_redis.hset = AsyncMock()

        await appconfig.sync_to_redis(db_session, mock_redis)

        await_args = mock_redis.hset.await_args
        assert await_args is not None
        assert await_args.kwargs["mapping"]["ctf.team_size"] == "7"
