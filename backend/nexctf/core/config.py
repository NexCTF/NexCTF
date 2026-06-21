import os
import secrets
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    PostgresDsn,
    RedisDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    BACKEND_HOST: str = "http://localhost:8000"
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin"
    DEFAULT_ADMIN_TOKEN: str | None = None

    @model_validator(mode="after")
    def require_secret_key_in_production(self) -> "Settings":
        if self.ENVIRONMENT != "development" and "SECRET_KEY" not in os.environ:
            raise ValueError(
                "SECRET_KEY must be explicitly set via the SECRET_KEY environment "
                "variable in non-development environments. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self

    # Number of trusted reverse proxies in front of the application.
    # 0 = no proxy (use the direct connection IP, ignore X-Forwarded-For).
    # N = N trusted proxies; the client IP is read N entries from the right of
    #     X-Forwarded-For (the leftmost entries are client-controlled and spoofable).
    # Adjust this to match your deployment topology.
    TRUSTED_PROXY_COUNT: int = 1

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    POSTGRES_TLS: bool = False

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn(
            MultiHostUrl.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
                query="ssl=require" if self.POSTGRES_TLS else None,
            )
        )

    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_TLS: bool = False

    @computed_field
    @property
    def REDIS_URL(self) -> RedisDsn:
        scheme = "rediss" if self.REDIS_TLS else "redis"
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return RedisDsn(
            f"{scheme}://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        )

    S3_HOST: str
    S3_PORT: int
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_TLS: bool = False
    S3_PUBLIC_URL: str | None = (
        None  # public-facing URL for presigned URLs (browser-accessible)
    )

    @computed_field
    @property
    def S3_URL(self) -> str:
        scheme = "https" if self.S3_TLS else "http"
        return f"{scheme}://{self.S3_HOST}:{self.S3_PORT}"

    @computed_field
    @property
    def S3_PRESIGN_URL(self) -> str:
        """Endpoint embedded in presigned URLs — must be reachable from the browser."""
        return self.S3_PUBLIC_URL or self.S3_URL


settings = Settings()  # type: ignore
