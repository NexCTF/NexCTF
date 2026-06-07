"""Run Alembic migrations for a nexctf plugin.

Usage:
    python scripts/run_plugin_migration.py <plugin_path> upgrade [revision]
    python scripts/run_plugin_migration.py <plugin_path> downgrade <revision>
    python scripts/run_plugin_migration.py <plugin_path> revision -m "message" [--autogenerate]
    python scripts/run_plugin_migration.py <plugin_path> current
    python scripts/run_plugin_migration.py <plugin_path> history

<plugin_path> may be absolute or relative to the backend/ directory.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SHARED_ALEMBIC = Path(__file__).resolve().parent / "plugin_alembic"

for _p in [str(_BACKEND), str(_BACKEND / "plugins_store")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5.5s [%(name)s] %(message)s",
    stream=sys.stderr,
)


def _make_config(plugin_dir: Path) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_SHARED_ALEMBIC))
    cfg.set_main_option("version_locations", str(plugin_dir / "alembic" / "versions"))
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Alembic migrations for a nexctf plugin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "plugin_dir",
        type=Path,
        help="Plugin directory (absolute or relative to backend/)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upgrade", help="Apply migrations")
    up.add_argument("revision", nargs="?", default="head")

    dn = sub.add_parser("downgrade", help="Revert migrations")
    dn.add_argument("revision", default="-1")

    rev = sub.add_parser("revision", help="Generate a new migration")
    rev.add_argument("-m", "--message", required=True)
    rev.add_argument("--autogenerate", action="store_true")

    sub.add_parser("current", help="Show current revision")
    sub.add_parser("history", help="Show revision history")

    args = parser.parse_args()

    plugin_dir = args.plugin_dir
    if not plugin_dir.is_absolute():
        plugin_dir = _BACKEND / plugin_dir

    os.environ["NEXCTF_PLUGIN_DIR"] = str(plugin_dir)
    cfg = _make_config(plugin_dir)

    match args.cmd:
        case "upgrade":
            command.upgrade(cfg, args.revision)
        case "downgrade":
            command.downgrade(cfg, args.revision)
        case "revision":
            command.revision(cfg, message=args.message, autogenerate=args.autogenerate)
        case "current":
            command.current(cfg)
        case "history":
            command.history(cfg)


main()
