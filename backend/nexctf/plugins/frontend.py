"""Registry of plugin-provided frontend bundles."""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from nexctf.plugins.declare import FrontendDef, PageDef

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Asset:
    """One served file, the name it is served under and its hashes."""

    name: str
    path: Path
    integrity: str
    version: str
    media_type: str


@dataclass(frozen=True)
class Bundle:
    """A script, its optional stylesheet, and the slots and pages it provides."""

    script: Asset
    style: Asset | None
    slots: list[str]
    pages: list[PageDef]

    def asset(self, name: str) -> Asset | None:
        """Return the script or stylesheet served under ``name``."""
        return next(
            (a for a in (self.script, self.style) if a and a.name == name), None
        )


@dataclass
class FrontendEntry:
    """A plugin's public and admin-only bundles."""

    key: str
    challenge_types: list[str] | None = None
    user: Bundle | None = None
    admin: Bundle | None = None
    missing: list[str] = field(default_factory=list)

    def bundle(self, admin: bool) -> Bundle | None:
        """Return the admin-only bundle, or the public one."""
        return self.admin if admin else self.user


def _load_asset(owner: str, dist_dir: Path, name: str, media_type: str) -> Asset | None:
    """Return the file ``name`` in ``dist_dir``, or None if it is absent."""
    path = (dist_dir / name).resolve()
    if not path.is_file():
        logger.warning(
            "plugin.frontend.missing key=%s path=%s "
            "(build the bundle and ship frontend/dist as package data)",
            owner,
            path,
        )
        return None
    digest = hashlib.sha384(path.read_bytes())
    return Asset(
        name=name,
        path=path,
        integrity=f"sha384-{base64.b64encode(digest.digest()).decode()}",
        version=digest.hexdigest()[:12],
        media_type=media_type,
    )


def _bundle(
    assets: dict[str, Asset | None],
    script: str | None,
    style: str | None,
    slots: list[str],
    pages: list[PageDef],
) -> Bundle | None:
    """Return the bundle whose script loaded; a missing stylesheet is left out."""
    loaded = assets.get(script) if script else None
    if loaded is None:
        return None
    return Bundle(
        script=loaded,
        style=assets.get(style) if style else None,
        slots=slots,
        pages=pages,
    )


class FrontendRegistry:
    """Maps plugin keys to their compiled frontend bundles."""

    def __init__(self) -> None:
        self._entries: dict[str, FrontendEntry] = {}

    def add(self, frontend: FrontendDef, owner: str) -> None:
        """Register the prebuilt bundles of plugin ``owner``.

        Args:
            frontend: The bundle declaration.
            owner: The plugin key, which also names the bundle's URL.
        """
        declared = (
            (frontend.entry_file, "text/javascript"),
            (frontend.entry_css, "text/css"),
            (frontend.admin_entry_file, "text/javascript"),
            (frontend.admin_entry_css, "text/css"),
        )
        assets = {
            name: _load_asset(owner, frontend.dist_dir, name, media_type)
            for name, media_type in declared
            if name
        }
        self._entries[owner] = FrontendEntry(
            key=owner,
            challenge_types=frontend.challenge_types,
            user=_bundle(
                assets,
                frontend.entry_file,
                frontend.entry_css,
                frontend.slots,
                frontend.user_pages,
            ),
            admin=_bundle(
                assets,
                frontend.admin_entry_file,
                frontend.admin_entry_css,
                frontend.admin_slots,
                frontend.admin_pages,
            ),
            missing=[name for name, asset in assets.items() if asset is None],
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
