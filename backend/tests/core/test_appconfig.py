"""Tests for the config store's Redis mirror and value resolution."""

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


class TestGetWithOverrides:
    """Values that fail validation resolve to the code default."""

    def test_unusable_value_falls_back(self) -> None:
        assert appconfig.get_with_overrides(
            "ctf.team_size", {"ctf.team_size": "x"}
        ) == (appconfig.get_with_overrides("ctf.team_size", {}))

    def test_raw_value_is_kept_without_sanitize(self) -> None:
        overrides = {"visibility.scoreboard": "hiden"}
        value = appconfig.get_with_overrides(
            "visibility.scoreboard", overrides, sanitize=False
        )
        assert value == "hiden"

    def test_on_off_are_understood(self) -> None:
        """NEXCTF-14: on/off must not fall back to the opposite default."""
        assert (
            appconfig.get_with_overrides(
                "ctf.allow_registration", {"ctf.allow_registration": "off"}
            )
            is False
        )
        assert (
            appconfig.get_with_overrides("captcha.enabled", {"captcha.enabled": "on"})
            is True
        )
