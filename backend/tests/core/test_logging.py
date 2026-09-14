"""Unit tests for nexctf.core.logging (toolsets wiring, file handling)."""

import json
import logging
import time

import pytest
from fastapi_toolsets.logger import SharedRotatingFileHandler
from fastapi_toolsets.logger.config import owned_handlers

from nexctf.core.config import settings
from nexctf.core.logging import _PROPAGATE_LOGGERS, log_context, setup_logging


@pytest.fixture(autouse=True)
def restore_logging():
    """Undo what setup_logging does to the loggers, for the next test."""
    root = logging.getLogger()
    level = root.level
    taken_over = {
        name: (lg.handlers[:], lg.level, lg.propagate)
        for name, lg in ((n, logging.getLogger(n)) for n in _PROPAGATE_LOGGERS)
    }
    yield
    for handler in owned_handlers():
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)
    for name, (handlers, lvl, propagate) in taken_over.items():
        taken = logging.getLogger(name)
        taken.handlers, taken.level, taken.propagate = handlers, lvl, propagate


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Enable file logging into a temporary directory."""
    monkeypatch.setattr(settings, "LOG_FILES", True)
    monkeypatch.setattr(settings, "LOG_DIR", str(tmp_path))
    return tmp_path


def _file_handlers() -> list[SharedRotatingFileHandler]:
    return [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, SharedRotatingFileHandler)
    ]


def test_files_off_keeps_the_stream_only(log_dir, monkeypatch):
    monkeypatch.setattr(settings, "LOG_FILES", False)

    setup_logging("api")

    assert list(log_dir.iterdir()) == []
    assert _file_handlers() == []


def test_uvicorn_access_is_silenced(log_dir):
    setup_logging("api")

    assert not logging.getLogger("uvicorn.access").isEnabledFor(logging.INFO)


def test_pgqueuer_records_reach_the_root_handlers(log_dir):
    pgqueuer = logging.getLogger("pgqueuer")
    pgqueuer.addHandler(logging.NullHandler())
    pgqueuer.propagate = False

    setup_logging("worker")

    assert pgqueuer.handlers == []
    assert pgqueuer.propagate is True


def test_sql_echo_follows_the_setting(log_dir, monkeypatch):
    monkeypatch.setattr(settings, "LOG_SQL", True)

    setup_logging("api")

    assert logging.getLogger("sqlalchemy.engine").isEnabledFor(logging.INFO)


def test_every_process_of_a_kind_shares_one_file(log_dir):
    setup_logging("api")

    logging.getLogger("nexctf.demo").warning("written")

    assert (log_dir / "api.log").exists()
    assert _file_handlers()[0].maxBytes == settings.LOG_MAX_BYTES
    assert _file_handlers()[0].backupCount == settings.LOG_BACKUPS


def test_json_file_carries_the_service_and_context(log_dir, monkeypatch):
    monkeypatch.setattr(settings, "LOG_FORMAT", "json")
    setup_logging("worker")

    with log_context(request_id="abc"):
        logging.getLogger("nexctf.demo").warning("hello %s", "world")
    _file_handlers()[0].flush()

    payload = json.loads((log_dir / "worker.log").read_text().splitlines()[-1])
    assert payload["service"] == "worker"
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "abc"


def test_console_file_has_no_colors(log_dir, monkeypatch):
    monkeypatch.setattr(settings, "LOG_FORMAT", "console")
    setup_logging("worker")

    logging.getLogger("nexctf.demo").warning("plain")
    _file_handlers()[0].flush()

    line = (log_dir / "worker.log").read_text()
    assert "\033[" not in line
    assert line.startswith(time.strftime("%Y-%m-%d"))


def test_setup_twice_keeps_a_single_file_handler(log_dir):
    setup_logging("api")
    setup_logging("api")

    assert len(_file_handlers()) == 1
