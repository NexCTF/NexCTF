"""Branded transactional email bodies.

Renders plain-text + HTML bodies for verification and password-reset emails,
branded with the CTF event name (``ctf.name``) and logo (``appearance.logo_url``)
resolved from the runtime config.
"""

from __future__ import annotations

from html import escape

from nexctf.core import appconfig


def _render(
    ctf_name: str,
    logo_url: str,
    *,
    heading: str,
    body: str,
    button_label: str,
    button_url: str,
) -> tuple[str, str]:
    """Build (text, html) bodies for a branded email.

    Args:
        ctf_name: Event name shown in the header.
        logo_url: Logo image URL; the ``<img>`` is omitted when empty.
        heading: Bold heading above the body text.
        body: One paragraph of explanatory text.
        button_label: Call-to-action button label.
        button_url: Call-to-action target URL.

    Returns:
        A ``(text, html)`` tuple.
    """
    text = (
        f"{heading}\n\n{body}\n\n{button_label}: {button_url}\n\n"
        f"If you did not request this, you can ignore this email.\n\n{ctf_name}"
    )

    safe_name = escape(ctf_name)
    logo_html = (
        f'<img src="{escape(logo_url, quote=True)}" alt="{safe_name}" '
        'style="max-height:48px;margin-bottom:16px" />'
        if logo_url
        else ""
    )
    html = (
        '<div style="font-family:sans-serif;max-width:480px;margin:0 auto;'
        'padding:24px;color:#0f172a">'
        f"{logo_html}"
        f'<h1 style="font-size:18px;margin:0 0 8px">{escape(heading)}</h1>'
        f'<p style="font-size:14px;line-height:1.5">{escape(body)}</p>'
        f'<p style="margin:24px 0"><a href="{escape(button_url, quote=True)}" '
        'style="display:inline-block;padding:10px 20px;background:#0f172a;'
        'color:#fff;text-decoration:none;border-radius:6px;font-size:14px">'
        f"{escape(button_label)}</a></p>"
        '<p style="font-size:12px;color:#64748b">'
        "If you did not request this, you can ignore this email.</p>"
        f'<p style="font-size:12px;color:#64748b">{safe_name}</p>'
        "</div>"
    )
    return text, html


def _branding(overrides: dict[str, str]) -> tuple[str, str]:
    """Resolve (ctf_name, logo_url) from a config overrides snapshot."""
    ctf_name = str(appconfig.get_with_overrides("ctf.name", overrides))
    logo_url = str(
        appconfig.get_with_overrides("appearance.logo_url", overrides)
    ).strip()
    return ctf_name, logo_url


async def build_verification_email(
    overrides: dict[str, str], link: str
) -> tuple[str, str, str]:
    """Build (subject, text, html) for the email-verification message."""
    ctf_name, logo_url = _branding(overrides)
    subject = f"Verify your email for {ctf_name}"
    text, html = _render(
        ctf_name,
        logo_url,
        heading=f"Verify your email for {ctf_name}",
        body=(
            "Confirm your email address to activate your account and start competing."
        ),
        button_label="Verify email",
        button_url=link,
    )
    return subject, text, html


async def build_password_reset_email(
    overrides: dict[str, str], link: str
) -> tuple[str, str, str]:
    """Build (subject, text, html) for the password-reset message."""
    ctf_name, logo_url = _branding(overrides)
    subject = f"Reset your {ctf_name} password"
    text, html = _render(
        ctf_name,
        logo_url,
        heading=f"Reset your {ctf_name} password",
        body=(
            "We received a request to reset your password. This link is valid "
            "for one hour."
        ),
        button_label="Reset password",
        button_url=link,
    )
    return subject, text, html
