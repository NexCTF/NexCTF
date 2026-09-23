"""Registry of plugin-provided frontend bundles."""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from nexctf.plugins.declare import FrontendDef

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Bundle:
    """One served bundle file, the name it is served under, its hashes and slots."""

    name: str
    path: Path
    integrity: str
    version: str
    slots: list[str]


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


def _load_bundle(
    owner: str, dist_dir: Path, name: str | None, slots: list[str]
) -> Bundle | None:
    """Return the bundle ``name`` in ``dist_dir``, or None when undeclared or absent."""
    if name is None:
        return None
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
    return Bundle(
        name=name,
        path=path,
        integrity=f"sha384-{base64.b64encode(digest.digest()).decode()}",
        version=digest.hexdigest()[:12],
        slots=slots,
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
        dist_dir = frontend.dist_dir
        user = _load_bundle(owner, dist_dir, frontend.entry_file, frontend.slots)
        admin = _load_bundle(
            owner, dist_dir, frontend.admin_entry_file, frontend.admin_slots
        )
        declared = ((frontend.entry_file, user), (frontend.admin_entry_file, admin))
        self._entries[owner] = FrontendEntry(
            key=owner,
            challenge_types=frontend.challenge_types,
            user=user,
            admin=admin,
            missing=[name for name, bundle in declared if name and bundle is None],
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
