"""Registry of plugin-provided frontend bundles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from nexctf.plugins.declare import FrontendDef

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
    """Maps plugin keys to their compiled frontend bundles."""

    def __init__(self) -> None:
        self._entries: dict[str, FrontendEntry] = {}

    def add(self, frontend: FrontendDef, owner: str) -> None:
        """Register the prebuilt bundle of plugin ``owner``.

        Args:
            frontend: The bundle declaration.
            owner: The plugin key, which also names the bundle's URL.
        """
        bundle = frontend.dist_dir / frontend.entry_file
        has_bundle = bundle.is_file()
        if not has_bundle:
            logger.warning(
                "plugin.frontend.missing key=%s path=%s "
                "(build the bundle and ship frontend/dist as package data)",
                owner,
                bundle,
            )
        self._entries[owner] = FrontendEntry(
            key=owner,
            dist_dir=frontend.dist_dir.resolve(),
            slots=frontend.slots,
            challenge_types=frontend.challenge_types,
            entry_file=frontend.entry_file,
            has_bundle=has_bundle,
        )

    def get_all(self) -> list[FrontendEntry]:
        """Return every registered frontend entry."""
        return list(self._entries.values())

    def get(self, key: str) -> FrontendEntry | None:
        """Return the entry for a key, or ``None`` if none is registered.

        Args:
            key: The plugin key to look up.
        """
        return self._entries.get(key)


frontend_registry = FrontendRegistry()
