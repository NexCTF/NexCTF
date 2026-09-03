"""Tests for the demo fixture context loaded in production by ``DEMO_DATA``."""

from nexctf.core.config import settings
from nexctf.fixtures import fixture_registry
from nexctf.fixtures.development import demo_user


def test_demo_context_holds_the_example_data_only() -> None:
    """Demo seeds the example CTF, without the dev SMTP/captcha config or API token."""
    names = {f.name for f in fixture_registry.get_by_context("demo")}
    assert {"challenge", "team", "submission"} <= names
    assert "config" not in names
    assert "token" not in names


def test_demo_users_cannot_log_in() -> None:
    """Demo accounts carry no password and never take the default admin name."""
    assert [v.func for v in fixture_registry.get_load_variants("user", "demo")] == [
        demo_user
    ]

    for user in demo_user():
        assert user.hashed_password is None
        assert user.username != settings.DEFAULT_ADMIN_USERNAME
