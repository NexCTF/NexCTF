from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FrontendEntry:
    """A plugin's compiled frontend bundle and the UI slots it fills."""

    key: str
    dist_dir: Path
    slots: list[str]
    challenge_types: list[str] | None = None
    entry_file: str = "bundle.js"


class FrontendRegistry:
    """Maps plugin keys to their compiled frontend bundles.

    Plugin authors call .register() from their plugin's __init__.py:
        frontend_registry.register(
            key="my_plugin",
            dist_dir=Path(__file__).parent / "frontend" / "dist",
            slots=["challenge_panel"],
            challenge_types=["container"],
        )
    """

    def __init__(self) -> None:
        self._entries: dict[str, FrontendEntry] = {}

    def register(
        self,
        key: str,
        dist_dir: Path,
        slots: list[str],
        challenge_types: list[str] | None = None,
        entry_file: str = "bundle.js",
    ) -> None:
        """Register a plugin's compiled frontend bundle.

        Args:
            key: Unique key identifying the plugin's frontend.
            dist_dir: Directory holding the compiled bundle.
            slots: UI slots the bundle fills (e.g. ``["challenge_panel"]``).
            challenge_types: Challenge types the bundle applies to, or ``None`` for all.
            entry_file: Bundle entry file name within ``dist_dir``.
        """
        self._entries[key] = FrontendEntry(
            key=key,
            dist_dir=dist_dir,
            slots=slots,
            challenge_types=challenge_types,
            entry_file=entry_file,
        )

    def get_all(self) -> list[FrontendEntry]:
        """Return every registered frontend entry."""
        return list(self._entries.values())

    def get(self, key: str) -> FrontendEntry | None:
        """Return the entry for a key, or ``None`` if none is registered.

        Args:
            key: The plugin frontend key to look up.

        Returns:
            The registered entry, or ``None`` if absent.
        """
        return self._entries.get(key)


frontend_registry = FrontendRegistry()


def build_plugin_frontend(plugin_dir: Path, plugin_name: str) -> None:
    """Build a plugin's frontend bundle if a ``frontend/`` directory is present.

    Args:
        plugin_dir: The plugin's root directory.
        plugin_name: The plugin name used for logging.
    """
    frontend_dir = plugin_dir / "frontend"
    if not frontend_dir.exists():
        return

    logger.info("plugin.frontend.install name=%s", plugin_name)
    node_modules = frontend_dir / "node_modules"
    result = subprocess.run(
        ["npm", "install", "--prefer-offline"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning(
            "plugin.frontend.install offline failed, retrying clean name=%s",
            plugin_name,
        )
        if node_modules.exists():
            shutil.rmtree(node_modules)
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        logger.error(
            "plugin.frontend.install failed name=%s\n%s",
            plugin_name,
            result.stderr or result.stdout,
        )
        return

    logger.info("plugin.frontend.build name=%s", plugin_name)
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(
            "plugin.frontend.build failed name=%s\n%s",
            plugin_name,
            result.stderr or result.stdout,
        )
        return

    logger.info("plugin.frontend.build complete name=%s", plugin_name)
