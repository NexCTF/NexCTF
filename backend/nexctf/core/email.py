"""SMTP email sending utility."""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib
from redis.asyncio import Redis

from nexctf.core import appconfig
from nexctf.exceptions import (
    EmailDisabledError,
    EmailMisconfiguredError,
    EmailSendError,
)

logger = logging.getLogger(__name__)


async def send_email(
    redis: Redis,
    to: str,
    subject: str,
    *,
    text: str,
    html: str | None = None,
) -> None:
    """Send an email through the configured SMTP server.

    Args:
        redis: Redis client used to read config overrides.
        to: Recipient email address.
        subject: Message subject.
        text: Plain-text body.
        html: Optional HTML body added as an alternative part.

    Raises:
        EmailDisabledError: When ``email.enabled`` is false.
        EmailMisconfiguredError: When required SMTP settings are missing.
        EmailSendError: When the SMTP server rejects or fails to deliver.
    """
    overrides = await appconfig.fetch_overrides(redis)

    if not appconfig.get_with_overrides("email.enabled", overrides):
        raise EmailDisabledError()

    host = str(appconfig.get_with_overrides("email.smtp_host", overrides)).strip()
    username = str(appconfig.get_with_overrides("email.smtp_username", overrides))
    password = str(appconfig.get_with_overrides("email.smtp_password", overrides))
    security = str(appconfig.get_with_overrides("email.security", overrides))
    from_address = str(
        appconfig.get_with_overrides("email.from_address", overrides)
    ).strip()
    from_name = str(appconfig.get_with_overrides("email.from_name", overrides)).strip()

    try:
        port = int(appconfig.get_with_overrides("email.smtp_port", overrides))
    except (TypeError, ValueError):
        port = 0

    if not host or not from_address or port < 1:
        logger.error(
            "email is enabled but smtp_host / smtp_port / from_address are not fully configured"
        )
        raise EmailMisconfiguredError()

    message = EmailMessage()
    message["From"] = f"{from_name} <{from_address}>" if from_name else from_address
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html is not None:
        message.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=host,
            port=port,
            username=username or None,
            password=password or None,
            use_tls=security == "tls",
            start_tls=security == "starttls",
            timeout=30.0,
        )
    except (aiosmtplib.SMTPException, OSError):
        logger.exception("SMTP send to %s failed", to)
        raise EmailSendError()


async def dispatch_email(
    redis: Redis,
    to: str,
    subject: str,
    *,
    text: str,
    html: str | None = None,
) -> None:
    """Send an email, logging and swallowing any failure."""
    try:
        await send_email(redis, to, subject, text=text, html=html)
    except Exception:
        logger.exception("background email dispatch to %s failed", to)
