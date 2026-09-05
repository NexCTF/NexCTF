"""Worker entrypoint tests.

Each check runs in a fresh interpreter: ``_DEFS`` is a module global that the
in-process conftest already populates through ``nexctf.main``.
"""

import subprocess
import sys

_RESOLVES_CONFIG = """
import nexctf.worker
from nexctf.util.datetime import event_timezone
assert event_timezone({}) == "UTC"
"""


def test_worker_import_registers_config_defs() -> None:
    subprocess.run([sys.executable, "-c", _RESOLVES_CONFIG], check=True)
