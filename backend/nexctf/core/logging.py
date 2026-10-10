"""Logging configuration shared by every NexCTF entrypoint."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi_toolsets.logger import (
    DEFAULT_PROPAGATE_LOGGERS,
    DEFAULT_QUIET_LOGGERS,
    LoggingConfig,
    bind_log_context,
    configure_logging,
    log_context,
)
from fastapi_toolsets.logger.context import mark_logged
from starlette.datastructures import Headers
from starlette.types import Scope

from nexctf.core.config import settings

__all__ = [
    "bind_log_context",
    "bind_user_context",
    "is_health_check",
    "log_context",
    "mark_logged",
    "setup_logging",
]

_QUIET_LOGGERS = (
    *DEFAULT_QUIET_LOGGERS,
    "aiobotocore",
    "boto3",
    "botocore",
    "s3transfer",
)

_PROPAGATE_LOGGERS = (*DEFAULT_PROPAGATE_LOGGERS, "pgqueuer")

_HEALTH_PATH = f"{settings.API_V1_STR}/info"
_LOOPBACK = frozenset({"127.0.0.1", "::1"})


def _log_file(process: str) -> Path | None:
    """Return the file this kind of process logs to, or None when files are off."""
    if not settings.LOG_FILES:
        return None
    return Path(settings.LOG_DIR) / f"{process}.log"


def bind_user_context(user_id: UUID, username: str) -> None:
    """Attach the user to every record logged for the rest of the request."""
    bind_log_context(user_id=str(user_id), username=username)


def is_health_check(scope: Scope) -> bool:
    """Whether a request is a local health check, kept out of the access log."""
    client = scope.get("client")
    return (
        scope.get("path") == _HEALTH_PATH
        and client is not None
        and client[0] in _LOOPBACK
        and "x-forwarded-for" not in Headers(scope=scope)
    )


def setup_logging(process: str) -> None:
    """Configure logging for the current process.

    Args:
        process: Name reported as the ``service`` field, also the log file
            stem. Every process of that kind shares the same rotated file.
    """
    configure_logging(
        LoggingConfig(
            level=settings.LOG_LEVEL,
            style=settings.LOG_FORMAT,
            service=process,
            file=_log_file(process),
            file_max_bytes=settings.LOG_MAX_BYTES,
            file_backups=settings.LOG_BACKUPS,
            propagate=_PROPAGATE_LOGGERS,
            access_log=True,
            quiet=_QUIET_LOGGERS,
            sql_echo=settings.LOG_SQL,
            otel=False,
        )
    )
