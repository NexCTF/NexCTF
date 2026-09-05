"""Tests for ALTCHA captcha verification (nexctf.core.captcha)."""

import time

import altcha
import pytest

from nexctf.core.captcha import (
    ALGORITHM,
    COST,
    _hmac_secret,
    create_challenge,
    verify_captcha,
)
from nexctf.exceptions import CaptchaInvalidError, CaptchaRequiredError

ENABLED = {"captcha.enabled": "true"}


def _solve(challenge: dict) -> str:
    """Solve a challenge dict the way the browser widget does."""
    parsed = altcha.Challenge.from_dict(challenge)
    solution = altcha.solve_challenge(parsed)
    assert solution is not None
    return altcha.Payload(challenge=parsed, solution=solution).to_base64()


@pytest.fixture
def token() -> str:
    return _solve(create_challenge())


async def test_disabled_skips_verification(redis):
    """With captcha off a missing token is fine, so the gate can be turned off."""
    await verify_captcha(redis, {"captcha.enabled": "false"}, None)


async def test_missing_token_raises_required(redis):
    """An enabled gate with no token tells the caller the token is missing."""
    with pytest.raises(CaptchaRequiredError):
        await verify_captcha(redis, ENABLED, None)


async def test_solved_challenge_verifies(redis, token):
    """A payload from the real issue/solve flow passes verification."""
    await verify_captcha(redis, ENABLED, token)


async def test_token_cannot_be_replayed(redis, token):
    """One solve buys exactly one action; the second use is rejected."""
    await verify_captcha(redis, ENABLED, token)

    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(redis, ENABLED, token)


async def test_malformed_token_rejected(redis):
    """A token the user made up is an invalid captcha, not a server error."""
    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(redis, ENABLED, "not-a-real-token")


async def test_unsolved_challenge_rejected(redis):
    """The challenge alone, without a valid counter, does not verify."""
    challenge = altcha.Challenge.from_dict(create_challenge())
    forged = altcha.Payload(
        challenge=challenge, solution=altcha.Solution(counter=0, derived_key="00" * 32)
    ).to_base64()

    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(redis, ENABLED, forged)


async def test_foreign_signature_rejected(redis):
    """A challenge signed with someone else's secret does not verify."""
    challenge = altcha.create_challenge(
        ALGORITHM, COST, expires_at=int(time.time()) + 300, hmac_secret="other-secret"
    )
    solution = altcha.solve_challenge(challenge)
    assert solution is not None
    forged = altcha.Payload(challenge=challenge, solution=solution).to_base64()

    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(redis, ENABLED, forged)


async def test_expired_challenge_rejected(redis):
    """A challenge past its expiry is rejected even though it is well signed."""
    challenge = altcha.create_challenge(
        ALGORITHM, COST, expires_at=int(time.time()) - 1, hmac_secret=_hmac_secret()
    )
    solution = altcha.solve_challenge(challenge)
    assert solution is not None
    stale = altcha.Payload(challenge=challenge, solution=solution).to_base64()

    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(redis, ENABLED, stale)


def test_challenge_carries_an_expiry_and_signature():
    """The widget needs a signed challenge; an unsigned one would be forgeable."""
    challenge = create_challenge()

    assert challenge["signature"]
    assert challenge["parameters"]["expiresAt"] > time.time()
