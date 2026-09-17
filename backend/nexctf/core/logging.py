"""Logging configuration shared by every NexCTF entrypoint."""

from __future__ import annotations

import json
import logging
import logging.config
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nexctf.core.config import settings

ACCESS_LOGGER = "nexctf.access"

_log_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "log_context", default=None
)

_process_name = "app"

# LogRecord attributes rendered explicitly or dropped; everything else on a
# record is caller-supplied ``extra`` and is emitted as a field.
_RESERVED_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

_LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
_RESET = "\033[0m"
_DIM = "\033[2m"

_NOISY_LOGGERS = (
    "aiobotocore",
    "asyncio",
    "boto3",
    "botocore",
    "httpcore",
    "httpx",
    "s3transfer",
    "urllib3",
)


def current_log_context() -> dict[str, Any]:
    """Return the context bound to the current task."""
    return _log_context.get() or {}


def bind_log_context(**values: Any) -> None:
    """Merge values into the context every record in this task carries."""
    _log_context.set({**current_log_context(), **values})


@contextmanager
def log_context(**values: Any) -> Iterator[None]:
    """Bind values for the duration of the block, then restore the previous set."""
    token = _log_context.set({**current_log_context(), **values})
    try:
        yield
    finally:
        _log_context.reset(token)


def _record_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Return the caller-supplied fields attached to a record."""
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_ATTRS and not key.startswith("_")
    }


class ContextFilter(logging.Filter):
    """Attach the current request context to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in current_log_context().items():
            if value is not None and not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """Render a record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        stamp = datetime.fromtimestamp(record.created, UTC).isoformat(
            timespec="milliseconds"
        )
        # Caller fields first: the five base keys below are the schema log
        # shippers key on, so an extra of the same name never displaces one.
        payload: dict[str, Any] = _record_fields(record)
        payload |= {
            "timestamp": stamp.replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "process": _process_name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Render a record as one human-readable line, colourised by level."""

    def __init__(self, *, colors: bool) -> None:
        super().__init__()
        self.colors = colors

    def format(self, record: logging.LogRecord) -> str:
        stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
        level = record.levelname.ljust(8)
        name = record.name
        if self.colors:
            level = f"{_LEVEL_COLORS.get(record.levelname, '')}{level}{_RESET}"
            name = f"{_DIM}{name}{_RESET}"
        line = f"{stamp}.{int(record.msecs):03d} {level} {name}: {record.getMessage()}"
        fields = " ".join(f"{k}={v}" for k, v in _record_fields(record).items())
        if fields:
            line = (
                f"{line} {_DIM}{fields}{_RESET}" if self.colors else f"{line} {fields}"
            )
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"
        return line


def _pid_is_live(pid: int) -> bool:
    """Report whether a process id belongs to a running process."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _prune_stale_files(directory: Path, prefix: str) -> None:
    """Delete ``<prefix>-<pid>.log*`` files left behind by dead processes."""
    for path in directory.glob(f"{prefix}-*.log*"):
        pid_part = path.name[len(prefix) + 1 :].split(".", 1)[0]
        if not pid_part.isdigit():
            continue
        pid = int(pid_part)
        if pid == os.getpid() or _pid_is_live(pid):
            continue
        path.unlink(missing_ok=True)


def _log_file(process: str, *, per_pid: bool) -> Path | None:
    """Return the file this process logs to, or None when files are disabled."""
    if not settings.LOG_DIR or os.environ.get("NEXCTF_TEST_MODE"):
        return None
    directory = Path(settings.LOG_DIR)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    if not per_pid:
        return directory / f"{process}.log"
    _prune_stale_files(directory, process)
    return directory / f"{process}-{os.getpid()}.log"


def _formatter_config() -> dict[str, Any]:
    """Build the formatter selected by ``LOG_FORMAT``."""
    if settings.LOG_FORMAT == "json":
        return {"()": "nexctf.core.logging.JsonFormatter"}
    return {
        "()": "nexctf.core.logging.ConsoleFormatter",
        "colors": sys.stderr.isatty(),
    }


def setup_logging(process: str, *, per_pid: bool = False) -> None:
    """Configure logging for the current process.

    Args:
        process: Name reported as the ``process`` field, also the log file stem.
        per_pid: Suffix the log file with the pid, for processes that run in
            several copies. A rotating file must have a single writer.
    """
    global _process_name
    _process_name = process

    level = settings.LOG_LEVEL.upper()
    handlers: dict[str, dict[str, Any]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "app",
            "filters": ["context"],
            "stream": "ext://sys.stderr",
        }
    }
    path = _log_file(process, per_pid=per_pid)
    if path:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "app",
            "filters": ["context"],
            "filename": str(path),
            "maxBytes": settings.LOG_MAX_BYTES,
            "backupCount": settings.LOG_BACKUPS,
            "encoding": "utf-8",
            "delay": True,
        }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"context": {"()": "nexctf.core.logging.ContextFilter"}},
            "formatters": {"app": _formatter_config()},
            "handlers": handlers,
            "root": {"handlers": list(handlers), "level": level},
            "loggers": {
                # Uvicorn installs its own handlers and formatter; empty
                # handler lists send its records to the root handlers instead.
                "uvicorn": {"handlers": [], "level": level, "propagate": True},
                "uvicorn.error": {"handlers": [], "level": level, "propagate": True},
                # Replaced by the access line the request middleware emits.
                "uvicorn.access": {
                    "handlers": [],
                    "level": "WARNING",
                    "propagate": False,
                },
                "sqlalchemy.engine": {
                    "level": "INFO" if settings.LOG_SQL else "WARNING",
                },
                **{name: {"level": "WARNING"} for name in _NOISY_LOGGERS},
            },
        }
    )
