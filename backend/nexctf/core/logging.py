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

from nexctf.core.config import settings

__all__ = [
    "bind_log_context",
    "bind_user_context",
    "log_context",
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


def _log_file(process: str) -> Path | None:
    """Return the file this kind of process logs to, or None when files are off."""
    if not settings.LOG_FILES:
        return None
    return Path(settings.LOG_DIR) / f"{process}.log"


def bind_user_context(user_id: UUID, username: str) -> None:
    """Attach the user to every record logged for the rest of the request."""
    bind_log_context(user_id=str(user_id), username=username)


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
