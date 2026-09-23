"""Plugin frontend manifests and the bundle files they point at."""

from __future__ import annotations

from fastapi.responses import FileResponse
from fastapi_toolsets.exceptions import NotFoundError

from nexctf.core.config import settings
from nexctf.plugins.frontend import frontend_registry
from nexctf.schema.plugin import PluginManifestEntry

_IMMUTABLE = "max-age=31536000, immutable"


def manifest(*, admin: bool) -> list[PluginManifestEntry]:
    """Return the bundles to load for visitors, or for admins only.

    Args:
        admin: Whether to list the admin-only bundles instead of the public ones.
    """
    base = f"{settings.API_V1_STR}{'/admin' if admin else ''}/plugins"
    return [
        PluginManifestEntry(
            key=entry.key,
            remote_entry=f"{base}/{entry.key}/frontend/{bundle.name}?v={bundle.version}",
            integrity=bundle.integrity,
            slots=bundle.slots,
            challenge_types=entry.challenge_types,
        )
        for entry in frontend_registry.get_all()
        if (bundle := entry.bundle(admin)) is not None
    ]


def bundle_response(
    key: str, file_path: str, version: str | None, *, admin: bool
) -> FileResponse:
    """Serve a plugin bundle, cached for good when requested at its current version.

    Raises:
        NotFoundError: If the plugin has no such bundle.
    """
    entry = frontend_registry.get(key)
    bundle = entry.bundle(admin) if entry is not None else None
    if bundle is None or bundle.name != file_path:
        raise NotFoundError()
    audience = "private" if admin else "public"
    cache = f"{audience}, {_IMMUTABLE}" if version == bundle.version else "no-cache"
    return FileResponse(
        bundle.path, media_type="text/javascript", headers={"Cache-Control": cache}
    )
