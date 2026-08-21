"""Tests for CAP captcha verification (nexctf.core.captcha)."""

import hashlib
import os
import time

import httpx
import pytest

from nexctf.core.captcha import verify_captcha
from nexctf.exceptions import (
    CaptchaInvalidError,
    CaptchaMisconfiguredError,
    CaptchaRequiredError,
)
from nexctf.fixtures.utils import admin_headers

CAP_URL = "http://127.0.0.1:3000"


def _config(**overrides: str) -> dict[str, str]:
    """A fully configured captcha override snapshot, minus a real site's keys."""
    return {
        "captcha.enabled": "true",
        "captcha.cap_api_url": CAP_URL,
        "captcha.cap_site_key": "site",
        "captcha.cap_secret_key": "secret",
        **overrides,
    }


def _fnv1a(text: str, state: int = 2166136261) -> int:
    """FNV-1a over `text`, resumable from a previous state."""
    for char in text:
        state = ((state ^ ord(char)) * 16777619) & 0xFFFFFFFF
    return state


def _prng(state: int, length: int) -> str:
    """xorshift32 hex stream of `length` chars, seeded from an FNV-1a state."""
    out = ""
    while len(out) < length:
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        out += format(state, "08x")
    return out[:length]


def _solve(token: str, count: int, size: int, difficulty: int) -> list[int]:
    """Find, for each sub-challenge, an int whose salted sha256 hits the target."""
    solutions = []
    token_hash = _fnv1a(token)
    for index in range(1, count + 1):
        salt_seed = _fnv1a(str(index), token_hash)
        salt = _prng(salt_seed, size)
        target = _prng(_fnv1a("d", salt_seed), difficulty)
        nonce = 0
        while (
            not hashlib.sha256(f"{salt}{nonce}".encode()).hexdigest().startswith(target)
        ):
            nonce += 1
        solutions.append(nonce)
    return solutions


@pytest.fixture(scope="module")
def cap_config():
    """Config overrides pointing at a throwaway CAP site, tuned for an instant solve."""
    admin_key = os.environ.get("CAP_ADMIN_KEY")
    with httpx.Client(base_url=CAP_URL, timeout=30.0) as client:
        in_ci = bool(os.environ.get("CI"))
        for _ in range(120 if in_ci else 20):
            try:
                headers = admin_headers(client, admin_key or "")
                break
            except httpx.TransportError:
                time.sleep(0.5)
        else:
            message = f"CAP not reachable at {CAP_URL}"
            pytest.fail(message) if in_ci else pytest.skip(message)

        created = client.post("/server/keys", headers=headers, json={"name": "pytest"})
        created.raise_for_status()
        site = created.json()

        tuned = client.put(
            f"/server/keys/{site['siteKey']}/config",
            headers=headers,
            json={"difficulty": 1, "challengeCount": 1},
        )
        tuned.raise_for_status()

        yield _config(
            **{
                "captcha.cap_site_key": site["siteKey"],
                "captcha.cap_secret_key": site["secretKey"],
            }
        )

        client.delete(f"/server/keys/{site['siteKey']}", headers=headers)


@pytest.fixture
def cap_token(cap_config) -> str:
    """A freshly solved, redeemable CAP token for the provisioned site."""
    site_key = cap_config["captcha.cap_site_key"]
    with httpx.Client(base_url=CAP_URL, timeout=30.0) as client:
        challenge = client.post(f"/{site_key}/challenge").json()
        spec = challenge["challenge"]
        solutions = _solve(challenge["token"], spec["c"], spec["s"], spec["d"])
        redeemed = client.post(
            f"/{site_key}/redeem",
            json={"token": challenge["token"], "solutions": solutions},
        ).json()
    assert redeemed.get("success"), f"CAP redeem failed: {redeemed}"
    return redeemed["token"]


async def test_disabled_skips_verification():
    """With captcha off a missing token is fine, so the gate can be turned off."""
    await verify_captcha({"captcha.enabled": "false"}, None)


@pytest.mark.parametrize(
    "missing",
    ["captcha.cap_api_url", "captcha.cap_site_key", "captcha.cap_secret_key"],
)
async def test_incomplete_config_raises(missing):
    """Enabled-but-incomplete config is a misconfiguration, not a rejected user."""
    with pytest.raises(CaptchaMisconfiguredError):
        await verify_captcha(_config(**{missing: ""}), "any-token")


async def test_missing_token_raises_required():
    """A configured gate with no token tells the caller the token is missing."""
    with pytest.raises(CaptchaRequiredError):
        await verify_captcha(_config(), None)


async def test_unreachable_server_raises_misconfigured():
    """An unreachable CAP host must not read as a failed captcha."""
    with pytest.raises(CaptchaMisconfiguredError):
        await verify_captcha(
            _config(**{"captcha.cap_api_url": "http://127.0.0.1:1"}), "any-token"
        )


async def test_solved_token_verifies(cap_config, cap_token):
    """A token from the real challenge/redeem flow passes verification."""
    await verify_captcha(cap_config, cap_token)


async def test_token_cannot_be_replayed(cap_config, cap_token):
    """CAP consumes the token on verify, so one solve buys exactly one action."""
    await verify_captcha(cap_config, cap_token)

    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(cap_config, cap_token)


async def test_malformed_token_rejected(cap_config):
    """A token the user made up is an invalid captcha, not a server error."""
    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(cap_config, "not-a-real-token")


async def test_token_from_another_site_rejected(cap_config, cap_token):
    """A token minted for one site key does not verify against another."""
    other = {**cap_config, "captcha.cap_site_key": "0000000000"}

    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(other, cap_token)


async def test_wrong_secret_reads_as_an_invalid_captcha(cap_config, cap_token):
    """A mistyped secret rejects every user rather than flagging the config."""
    wrong = {**cap_config, "captcha.cap_secret_key": "sk-wrong"}

    with pytest.raises(CaptchaInvalidError):
        await verify_captcha(wrong, cap_token)
