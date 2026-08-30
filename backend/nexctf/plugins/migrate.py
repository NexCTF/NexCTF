"""Alembic migrations for installed nexctf plugins.

Usage:
    nexctf-plugins upgrade                              # every plugin
    nexctf-plugins upgrade [rev] -p <plugin>
    nexctf-plugins downgrade <rev> -p <plugin>
    nexctf-plugins revision -m "msg" [--autogenerate] -p <plugin>
    nexctf-plugins current|history [-p <plugin>]

``<plugin>`` is the plugin's distribution name, e.g. ``nexctf-sandbox``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from nexctf.plugins.loader import (
    get_plugin_migrations,
    load_plugin_registries,
    plugin_key,
    version_table,
)

_SHARED_ALEMBIC = Path(__file__).resolve().parent / "migrations"

logger = logging.getLogger("plugin.migration")


def _make_config(key: str, versions_dir: Path, owned_tables: frozenset[str]) -> Config:
    """Build an Alembic config targeting one plugin's migrations."""
    cfg = Config()
    cfg.set_main_option("script_location", str(_SHARED_ALEMBIC))
    cfg.set_main_option("version_locations", str(versions_dir))
    cfg.attributes["version_table"] = version_table(key)
    cfg.attributes["owned_tables"] = owned_tables
    return cfg


def _parse_args() -> argparse.Namespace:
    """Define the command line and parse it."""
    parser = argparse.ArgumentParser(
        prog="nexctf-plugins",
        description="Run Alembic migrations for installed nexctf plugins.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-p",
        "--plugin",
        help="Plugin distribution name; defaults to every installed plugin",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upgrade", help="Apply migrations", parents=[common])
    up.add_argument("revision", nargs="?", default="head")

    dn = sub.add_parser("downgrade", help="Revert migrations", parents=[common])
    dn.add_argument("revision")

    rev = sub.add_parser("revision", help="Generate a new migration", parents=[common])
    rev.add_argument("-m", "--message", required=True)
    rev.add_argument("--autogenerate", action="store_true")

    sub.add_parser("current", help="Show current revision", parents=[common])
    sub.add_parser("history", help="Show revision history", parents=[common])
    return parser.parse_args()


def main() -> None:
    """Run the requested Alembic command against the selected plugins."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-5.5s [%(name)s] %(message)s",
        stream=sys.stderr,
    )
    args = _parse_args()

    load_plugin_registries()
    targets = get_plugin_migrations()
    if args.plugin:
        key = plugin_key(args.plugin)
        if key not in targets:
            raise SystemExit(
                f"plugin {args.plugin!r} has no migrations "
                f"(installed with migrations: {', '.join(targets) or 'none'})"
            )
        targets = {key: targets[key]}
    if args.cmd in ("revision", "downgrade") and len(targets) != 1:
        raise SystemExit(f"{args.cmd} needs a single plugin — pass --plugin")

    for key, (versions_dir, owned_tables) in targets.items():
        logger.info("plugin.migration name=%s cmd=%s", key, args.cmd)
        cfg = _make_config(key, versions_dir, owned_tables)
        match args.cmd:
            case "upgrade":
                command.upgrade(cfg, args.revision)
            case "downgrade":
                command.downgrade(cfg, args.revision)
            case "revision":
                command.revision(
                    cfg, message=args.message, autogenerate=args.autogenerate
                )
            case "current":
                command.current(cfg)
            case "history":
                command.history(cfg)
