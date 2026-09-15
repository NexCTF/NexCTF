"""Unit tests for nexctf.core.logging (formatters, context, file handling)."""

import json
import logging
import os
import sys

import pytest

from nexctf.core import logging as nexctf_logging
from nexctf.core.config import settings
from nexctf.core.logging import (
    ConsoleFormatter,
    ContextFilter,
    JsonFormatter,
    log_context,
    setup_logging,
)


@pytest.fixture(autouse=True)
def restore_logging():
    """Undo what setup_logging does to the root logger, for the next test."""
    root = logging.getLogger()
    original = root.handlers[:]
    level = root.level
    access = logging.getLogger("uvicorn.access")
    access_state = (access.handlers[:], access.level, access.propagate)
    yield
    for handler in root.handlers[:]:
        if handler not in original:
            root.removeHandler(handler)
            handler.close()
    for handler in original:
        if handler not in root.handlers:
            root.addHandler(handler)
    root.setLevel(level)
    access.handlers, access.level, access.propagate = access_state


@pytest.fixture
def record() -> logging.LogRecord:
    return logging.LogRecord(
        name="nexctf.demo",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Enable file logging into a temporary directory."""
    monkeypatch.setattr(settings, "LOG_DIR", str(tmp_path))
    monkeypatch.delenv("NEXCTF_TEST_MODE", raising=False)
    return tmp_path


def _filtered(record: logging.LogRecord) -> logging.LogRecord:
    ContextFilter().filter(record)
    return record


def test_json_carries_the_common_fields(record):
    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "nexctf.demo"
    assert payload["message"] == "hello world"
    assert set(payload) >= {"timestamp", "level", "logger", "process", "message"}


def test_access_record_uses_the_same_field_set_as_an_app_record(record):
    access = logging.LogRecord(
        name="nexctf.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    access.__dict__.update(
        {"method": "GET", "path": "/api/v1/info", "status": 200, "duration_ms": 1.5}
    )

    app_payload = json.loads(JsonFormatter().format(record))
    access_payload = json.loads(JsonFormatter().format(access))

    assert set(app_payload) <= set(access_payload)
    assert access_payload["method"] == "GET"
    assert access_payload["duration_ms"] == 1.5


def test_context_is_attached_to_every_record(record):
    with log_context(request_id="abc", ip="10.0.0.1"):
        payload = json.loads(JsonFormatter().format(_filtered(record)))

    assert payload["request_id"] == "abc"
    assert payload["ip"] == "10.0.0.1"


def test_context_is_dropped_after_the_block(record):
    with log_context(request_id="abc"):
        pass

    assert "request_id" not in json.loads(JsonFormatter().format(_filtered(record)))


def test_console_renders_message_and_fields(record):
    record.__dict__["status"] = 200

    line = ConsoleFormatter(colors=False).format(record)

    assert "nexctf.demo: hello world" in line
    assert "status=200" in line


def test_exception_is_rendered_into_the_exception_field():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="nexctf.demo",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_test_mode_writes_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("NEXCTF_TEST_MODE", "1")

    setup_logging("api", per_pid=True)

    assert list(tmp_path.iterdir()) == []


def test_uvicorn_access_is_silenced(log_dir):
    setup_logging("api")

    access = logging.getLogger("uvicorn.access")

    assert access.handlers == []
    assert access.propagate is False


def test_file_is_named_after_the_process_and_pid(log_dir):
    setup_logging("api", per_pid=True)

    logging.getLogger("nexctf.demo").warning("written")

    assert (log_dir / f"api-{os.getpid()}.log").exists()


def test_stale_pid_files_are_pruned_and_live_ones_kept(log_dir, monkeypatch):
    stale = log_dir / "api-999999.log"
    stale.write_text("old\n")
    live = log_dir / f"api-{os.getpid()}.log"
    live.write_text("mine\n")
    other = log_dir / "scheduler.log"
    other.write_text("not mine to prune\n")
    monkeypatch.setattr(nexctf_logging, "_pid_is_live", lambda pid: pid == os.getpid())

    setup_logging("api", per_pid=True)

    assert not stale.exists()
    assert live.exists()
    assert other.exists()
