"""Tests for the cookie credential validator and TOTP check in nexctf.api.security."""

import time
import uuid

import pyotp
import pytest
from fastapi_toolsets.exceptions import UnauthorizedError
from starlette.requests import Request

from nexctf.api.security import (
    TOTP_LAST_STEP_KEY_PREFIX,
    TOTP_LAST_STEP_TTL,
    _verify_cookie,
    verify_totp_once,
)


class TestVerifyCookie:
    """A signed cookie whose payload is malformed is rejected, not a crash."""

    @pytest.mark.parametrize(
        "credential",
        [
            "not-a-uuid:1",  # user id does not parse
            "00000000-0000-4000-8001-000000000002:notanint",  # version does not parse
            "no-separator",  # does not split into two parts
        ],
    )
    async def test_malformed_payload_is_unauthorized(self, credential: str) -> None:
        with pytest.raises(UnauthorizedError):
            await _verify_cookie(
                credential, session_id="irrelevant", request=Request({"type": "http"})
            )


def _step_keys(redis, user_id):
    return redis.scan_iter(f"{TOTP_LAST_STEP_KEY_PREFIX}{user_id}:*")


class TestVerifyTotpOnce:
    """A TOTP code is accepted once, and never after a newer one."""

    @pytest.fixture
    async def user_id(self, redis):
        user_id = uuid.uuid4()
        yield user_id
        async for key in _step_keys(redis, user_id):
            await redis.delete(key)

    @pytest.fixture
    def totp(self) -> pyotp.TOTP:
        return pyotp.TOTP(pyotp.random_base32())

    async def test_accepts_a_valid_code_and_records_its_step(
        self, redis, user_id, totp
    ):
        assert await verify_totp_once(redis, user_id, totp.secret, totp.now())
        [key] = [key async for key in _step_keys(redis, user_id)]
        assert 0 < await redis.ttl(key) <= TOTP_LAST_STEP_TTL

    async def test_refuses_a_wrong_code(self, redis, user_id, totp):
        assert not await verify_totp_once(redis, user_id, totp.secret, "000000")

    async def test_refuses_a_replayed_code(self, redis, user_id, totp):
        code = totp.now()
        assert await verify_totp_once(redis, user_id, totp.secret, code)
        assert not await verify_totp_once(redis, user_id, totp.secret, code)

    async def test_refuses_an_older_code_after_a_newer_one(self, redis, user_id, totp):
        now = int(time.time())
        assert await verify_totp_once(redis, user_id, totp.secret, totp.at(now + 30))
        assert not await verify_totp_once(redis, user_id, totp.secret, totp.at(now))

    async def test_accepts_a_newer_code_after_an_older_one(self, redis, user_id, totp):
        now = int(time.time())
        assert await verify_totp_once(redis, user_id, totp.secret, totp.at(now))
        assert await verify_totp_once(redis, user_id, totp.secret, totp.at(now + 30))

    async def test_a_new_secret_is_not_held_to_the_old_one(self, redis, user_id, totp):
        new = pyotp.TOTP(pyotp.random_base32())
        now = int(time.time())
        assert await verify_totp_once(redis, user_id, totp.secret, totp.at(now + 30))
        assert await verify_totp_once(redis, user_id, new.secret, new.at(now))
