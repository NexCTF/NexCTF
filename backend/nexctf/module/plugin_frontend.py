"""Plugin frontend manifests and the bundle files they point at."""

from __future__ import annotations

from fastapi.responses import FileResponse
from fastapi_toolsets.exceptions import NotFoundError

from nexctf.core.config import settings
from nexctf.plugins.frontend import Asset, Bundle, FrontendEntry, frontend_registry
from nexctf.schema.plugin import PluginManifestEntry, PluginPage, PluginStylesheet

_IMMUTABLE = "max-age=31536000, immutable"


def _entry(base: str, entry: FrontendEntry, bundle: Bundle) -> PluginManifestEntry:
    def url(asset: Asset) -> str:
        return f"{base}/{entry.key}/frontend/{asset.name}?v={asset.version}"

    style = bundle.style
    return PluginManifestEntry(
        key=entry.key,
        remote_entry=url(bundle.script),
        integrity=bundle.script.integrity,
        stylesheet=style
        and PluginStylesheet(url=url(style), integrity=style.integrity),
        slots=bundle.slots,
        pages=[PluginPage.model_validate(page) for page in bundle.pages],
        challenge_types=entry.challenge_types,
    )


def manifest(*, admin: bool) -> list[PluginManifestEntry]:
    """Return the bundles to load for visitors, or for admins only.

    Args:
        admin: Whether to list the admin-only bundles instead of the public ones.
    """
    base = f"{settings.API_V1_STR}{'/admin' if admin else ''}/plugins"
    return [
        _entry(base, entry, bundle)
        for entry in frontend_registry.get_all()
        if (bundle := entry.bundle(admin)) is not None
    ]


def bundle_response(
    key: str, file_path: str, version: str | None, *, admin: bool
) -> FileResponse:
    """Serve a bundle's script or stylesheet, cached for good at its current version.

    Raises:
        NotFoundError: If the plugin's bundle has no such file.
    """
    entry = frontend_registry.get(key)
    bundle = entry.bundle(admin) if entry is not None else None
    asset = bundle.asset(file_path) if bundle is not None else None
    if asset is None:
        raise NotFoundError()
    audience = "private" if admin else "public"
    cache = f"{audience}, {_IMMUTABLE}" if version == asset.version else "no-cache"
    return FileResponse(
        asset.path, media_type=asset.media_type, headers={"Cache-Control": cache}
    )
