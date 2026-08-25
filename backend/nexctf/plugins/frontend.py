"""Registry of plugin-provided frontend bundles."""

from __future__ import annotations

import logging
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
    has_bundle: bool = True


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
        """Register a plugin's prebuilt frontend bundle.

        Args:
            key: Unique key identifying the plugin's frontend.
            dist_dir: Directory holding the compiled bundle.
            slots: UI slots the bundle fills (e.g. ``["challenge_panel"]``).
            challenge_types: Challenge types the bundle applies to, or ``None`` for all.
            entry_file: Bundle entry file name within ``dist_dir``.
        """
        has_bundle = (dist_dir / entry_file).is_file()
        if not has_bundle:
            logger.warning(
                "plugin.frontend.missing key=%s path=%s "
                "(build the bundle and ship frontend/dist as package data)",
                key,
                dist_dir / entry_file,
            )
        self._entries[key] = FrontendEntry(
            key=key,
            dist_dir=dist_dir.resolve(),
            slots=slots,
            challenge_types=challenge_types,
            entry_file=entry_file,
            has_bundle=has_bundle,
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
