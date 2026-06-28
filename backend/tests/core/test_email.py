"""Tests for the SMTP send service (nexctf.core.email)."""

from email.message import EmailMessage
from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest

from nexctf.core.email import dispatch_email, send_email
from nexctf.exceptions import (
    EmailDisabledError,
    EmailMisconfiguredError,
    EmailSendError,
)

CONFIGURED = {
    "email.enabled": "true",
    "email.smtp_host": "smtp.example.com",
    "email.smtp_port": "587",
    "email.smtp_username": "user",
    "email.smtp_password": "secret",
    "email.security": "starttls",
    "email.from_address": "ctf@example.com",
    "email.from_name": "NexCTF",
}


def _patch_overrides(overrides: dict[str, str]):
    """Patch fetch_overrides so send_email reads the given config."""
    return patch(
        "nexctf.core.email.appconfig.fetch_overrides",
        new=AsyncMock(return_value=overrides),
    )


def _patch_smtp():
    """Patch aiosmtplib.send so no real SMTP connection is opened."""
    return patch("nexctf.core.email.aiosmtplib.send", new=AsyncMock())


async def test_send_email_disabled_raises():
    """A send is refused when email.enabled is false rather than silently dropped."""
    with _patch_overrides({"email.enabled": "false"}):
        with pytest.raises(EmailDisabledError):
            await send_email(AsyncMock(), "to@example.com", "Hi", text="body")


@pytest.mark.parametrize(
    "missing",
    [
        {**CONFIGURED, "email.smtp_host": ""},
        {**CONFIGURED, "email.from_address": ""},
        {**CONFIGURED, "email.smtp_port": "0"},
        {**CONFIGURED, "email.smtp_port": "not-a-number"},
    ],
)
async def test_send_email_missing_required_raises(missing):
    """Enabled-but-incomplete config is a misconfiguration, not a send attempt."""
    with _patch_overrides(missing), _patch_smtp() as mock_send:
        with pytest.raises(EmailMisconfiguredError):
            await send_email(AsyncMock(), "to@example.com", "Hi", text="body")
    mock_send.assert_not_called()


async def test_send_email_success_passes_resolved_config():
    """The resolved host/port/credentials and a well-formed message reach aiosmtplib."""
    with _patch_overrides(CONFIGURED), _patch_smtp() as mock_send:
        await send_email(
            AsyncMock(),
            "player@example.com",
            "Welcome",
            text="hello",
            html="<p>hello</p>",
        )

    mock_send.assert_awaited_once()
    message, kwargs = mock_send.await_args.args[0], mock_send.await_args.kwargs
    assert kwargs["hostname"] == "smtp.example.com"
    assert kwargs["port"] == 587
    assert kwargs["username"] == "user"
    assert kwargs["password"] == "secret"
    assert kwargs["start_tls"] is True
    assert kwargs["use_tls"] is False
    assert isinstance(message, EmailMessage)
    assert message["To"] == "player@example.com"
    assert message["Subject"] == "Welcome"
    assert message["From"] == "NexCTF <ctf@example.com>"
    assert message.get_content_type() == "multipart/alternative"


async def test_send_email_tls_mode_uses_implicit_tls():
    """security='tls' selects implicit TLS, not STARTTLS."""
    with (
        _patch_overrides({**CONFIGURED, "email.security": "tls"}),
        _patch_smtp() as mock_send,
    ):
        await send_email(AsyncMock(), "to@example.com", "Hi", text="body")
    kwargs = mock_send.await_args.kwargs
    assert kwargs["use_tls"] is True
    assert kwargs["start_tls"] is False


async def test_send_email_no_credentials_passes_none():
    """Empty username/password become None so aiosmtplib skips auth."""
    bare = {**CONFIGURED, "email.smtp_username": "", "email.smtp_password": ""}
    with _patch_overrides(bare), _patch_smtp() as mock_send:
        await send_email(AsyncMock(), "to@example.com", "Hi", text="body")
    kwargs = mock_send.await_args.kwargs
    assert kwargs["username"] is None
    assert kwargs["password"] is None


async def test_send_email_smtp_failure_wrapped():
    """An SMTP-layer failure surfaces as EmailSendError, not the raw library error."""
    smtp_fail = patch(
        "nexctf.core.email.aiosmtplib.send",
        new=AsyncMock(side_effect=aiosmtplib.SMTPException("boom")),
    )
    with _patch_overrides(CONFIGURED), smtp_fail, pytest.raises(EmailSendError):
        await send_email(AsyncMock(), "to@example.com", "Hi", text="body")


async def test_dispatch_email_swallows_failure():
    """Background dispatch must not propagate errors to an already-sent response."""
    with patch(
        "nexctf.core.email.send_email",
        new=AsyncMock(side_effect=EmailSendError()),
    ) as mock_send:
        await dispatch_email(AsyncMock(), "to@example.com", "Hi", text="body")
    mock_send.assert_awaited_once()
