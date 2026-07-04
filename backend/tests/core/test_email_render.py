"""Tests for branded email body rendering (nexctf.core.email_render)."""

from nexctf.core.email_render import (
    _render,
    build_password_reset_email,
    build_verification_email,
)

BRANDING = {"ctf.name": "MyCTF", "appearance.logo_url": "https://cdn/logo.png"}


def test_render_includes_heading_body_and_button():
    text, html = _render(
        "MyCTF",
        "https://cdn/logo.png",
        heading="Verify",
        body="Please confirm.",
        button_label="Go",
        button_url="https://app/x?token=abc",
    )
    assert "Verify" in text and "Please confirm." in text
    assert "https://app/x?token=abc" in text
    assert 'href="https://app/x?token=abc"' in html
    assert 'src="https://cdn/logo.png"' in html


def test_render_omits_logo_when_unset():
    _text, html = _render(
        "MyCTF", "", heading="H", body="B", button_label="Go", button_url="https://app"
    )
    assert "<img" not in html


async def test_verification_email_carries_brand_and_link():
    subject, text, html = await build_verification_email(
        BRANDING, "https://app/verify-email?token=tok"
    )
    assert "MyCTF" in subject
    assert "https://app/verify-email?token=tok" in text
    assert "https://app/verify-email?token=tok" in html
    assert "MyCTF" in html


async def test_password_reset_email_carries_brand_and_link():
    subject, text, html = await build_password_reset_email(
        BRANDING, "https://app/reset-password?token=tok"
    )
    assert "MyCTF" in subject
    assert "https://app/reset-password?token=tok" in html
