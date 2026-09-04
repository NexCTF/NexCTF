"""DOMAIN drives the public URLs, per the Caddyfile in scripts/start.sh."""

import pytest

from nexctf.core.config import Settings

REQUIRED = {
    "POSTGRES_SERVER": "db",
    "POSTGRES_USER": "postgres",
    "REDIS_HOST": "cache",
    "S3_HOST": "s3",
    "S3_PORT": "9000",
    "S3_BUCKET": "nexctf",
    "S3_ACCESS_KEY": "admin",
    "S3_SECRET_KEY": "admin",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    """Build Settings from an explicit environment, ignoring the repo .env."""

    def build(**overrides: str) -> Settings:
        for name in (
            "DOMAIN",
            "FRONTEND_HOST",
            "BACKEND_HOST",
            "S3_PUBLIC_URL",
            "BACKEND_CORS_ORIGINS",
        ):
            monkeypatch.delenv(name, raising=False)
        for name, value in (REQUIRED | overrides).items():
            monkeypatch.setenv(name, value)
        return Settings(_env_file=None)

    return build


def test_without_domain_keeps_dev_defaults(env) -> None:
    settings = env()
    assert settings.FRONTEND_HOST == "http://localhost:5173"
    assert settings.BACKEND_HOST == "http://localhost:8000"
    assert settings.S3_PRESIGN_URL == "http://s3:9000"


def test_domain_derives_public_urls(env) -> None:
    settings = env(DOMAIN="ctf.example.com")
    assert settings.FRONTEND_HOST == "https://ctf.example.com"
    assert settings.BACKEND_HOST == "https://ctf.example.com"
    assert settings.S3_PRESIGN_URL == "https://s3.ctf.example.com"
    assert settings.all_cors_origins == ["https://ctf.example.com"]


def test_empty_values_still_derive(env) -> None:
    settings = env(DOMAIN="ctf.example.com", FRONTEND_HOST="", S3_PUBLIC_URL="")
    assert settings.FRONTEND_HOST == "https://ctf.example.com"
    assert settings.S3_PRESIGN_URL == "https://s3.ctf.example.com"


def test_explicit_host_wins_over_domain(env) -> None:
    settings = env(DOMAIN="ctf.example.com", FRONTEND_HOST="https://play.example.com")
    assert settings.FRONTEND_HOST == "https://play.example.com"
    assert settings.BACKEND_HOST == "https://ctf.example.com"
