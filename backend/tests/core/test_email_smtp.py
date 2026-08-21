"""Integration tests for nexctf.core.email against a real SMTP server (mailpit)."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from nexctf.core.email import send_email
from nexctf.core.email_render import build_verification_email

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
API_URL = "http://127.0.0.1:8025/api/v1"

BASE_CONFIG = {
    "email.enabled": "true",
    "email.smtp_host": SMTP_HOST,
    "email.smtp_port": str(SMTP_PORT),
    "email.smtp_username": "",
    "email.smtp_password": "",
    "email.security": "none",
    "email.from_address": "ctf@example.com",
    "email.from_name": "NexCTF",
}


def _api(path: str) -> dict:
    """GET a mailpit API path and return the decoded JSON body."""
    with urllib.request.urlopen(f"{API_URL}{path}", timeout=10) as resp:
        return json.load(resp)


@pytest.fixture(scope="module", autouse=True)
def ensure_mailpit():
    """Wait for mailpit, skipping locally but failing in CI."""
    deadline = time.monotonic() + 15
    while True:
        try:
            _api("/info")
            return
        except urllib.error.URLError, OSError:
            if time.monotonic() >= deadline:
                break
            time.sleep(0.5)

    message = f"mailpit not reachable at {API_URL}"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture
def recipient() -> str:
    """Unique recipient per test so parallel workers never read each other's mail."""
    return f"{uuid.uuid4()}@test.invalid"


def _fetch(to: str) -> dict:
    """Return the single delivered message addressed to `to`."""
    found = _api("/search?query=" + urllib.parse.quote(f"to:{to}"))
    assert found["messages_count"] == 1, f"expected 1 message for {to}"
    return _api(f"/message/{found['messages'][0]['ID']}")


async def _send(overrides: dict[str, str], to: str, subject: str, **kwargs) -> None:
    """Run send_email with the given config overrides against mailpit."""
    with patch(
        "nexctf.core.email.appconfig.fetch_overrides",
        new=AsyncMock(return_value={**BASE_CONFIG, **overrides}),
    ):
        await send_email(AsyncMock(), to, subject, **kwargs)


async def test_multipart_message_delivered_intact(recipient):
    """Both alternative parts survive the round-trip, not just the last one."""
    await _send({}, recipient, "Welcome", text="plain body", html="<p>html body</p>")

    msg = _fetch(recipient)
    assert msg["Subject"] == "Welcome"
    assert msg["From"] == {"Name": "NexCTF", "Address": "ctf@example.com"}
    assert "plain body" in msg["Text"]
    assert "<p>html body</p>" in msg["HTML"]


async def test_text_only_message_has_no_html_part(recipient):
    """A text-only send does not gain an HTML part on the way out."""
    await _send({}, recipient, "Plain", text="just text")

    msg = _fetch(recipient)
    assert "just text" in msg["Text"]
    assert msg["HTML"] == ""


async def test_non_ascii_subject_and_name_round_trip(recipient):
    """Accented headers arrive decoded, so RFC 2047 encoding is applied correctly."""
    await _send(
        {"email.from_name": "Équipe NexCTF"},
        recipient,
        "Vérifiez votre e-mail",
        text="accentué: garçon",
    )

    msg = _fetch(recipient)
    assert msg["Subject"] == "Vérifiez votre e-mail"
    assert msg["From"]["Name"] == "Équipe NexCTF"
    assert "accentué: garçon" in msg["Text"]


async def test_from_name_with_comma_keeps_address_parseable(recipient):
    """An unquoted comma in the display name would swallow the address."""
    await _send({"email.from_name": "NexCTF, Team"}, recipient, "Hi", text="body")

    msg = _fetch(recipient)
    assert msg["From"] == {"Name": "NexCTF, Team", "Address": "ctf@example.com"}


async def test_credentials_are_accepted_by_the_server(recipient):
    """The AUTH exchange completes and still delivers, unlike the anonymous path."""
    await _send(
        {"email.smtp_username": "user", "email.smtp_password": "secret"},
        recipient,
        "Authed",
        text="body",
    )

    assert "body" in _fetch(recipient)["Text"]


async def test_verification_email_link_reaches_both_parts(recipient):
    """A rendered transactional email delivers its action link in text and HTML."""
    link = "https://ctf.example.com/verify?token=abc123"
    subject, text, html = await build_verification_email({}, link)
    await _send({}, recipient, subject, text=text, html=html)

    msg = _fetch(recipient)
    assert msg["Subject"] == subject
    assert link in msg["Text"]
    assert link in msg["HTML"]


async def test_verification_email_html_is_widely_supported(recipient):
    """Guard the template against CSS no client renders."""
    _, text, html = await build_verification_email({}, "https://ctf.example.com/v")
    await _send({}, recipient, "Compat", text=text, html=html)

    total = _api(f"/message/{_fetch(recipient)['ID']}/html-check")["Total"]
    assert total["Tests"] > 0, "html-check ran no tests"
    assert total["Unsupported"] < 5, f"unsupported CSS share too high: {total}"
