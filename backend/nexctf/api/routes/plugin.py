"""Plugin frontend manifest and static bundle serving."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi_toolsets.exceptions import NotFoundError

from nexctf.plugins.frontend import frontend_registry
from nexctf.schema.plugin import PluginManifestEntry

plugin_router = APIRouter(prefix="/plugins", tags=["Plugins"])


@plugin_router.get("/manifest")
async def get_plugin_manifest() -> list[PluginManifestEntry]:
    return [
        PluginManifestEntry(
            key=entry.key,
            remote_entry=f"/api/v1/plugins/{entry.key}/frontend/{entry.entry_file}",
            slots=entry.slots,
            challenge_types=entry.challenge_types,
        )
        for entry in frontend_registry.get_all()
        if (entry.dist_dir / entry.entry_file).exists()
    ]


@plugin_router.get("/{plugin_key}/frontend/{file_path:path}", include_in_schema=False)
async def serve_plugin_frontend(plugin_key: str, file_path: str) -> FileResponse:
    entry = frontend_registry.get(plugin_key)
    if entry is None:
        raise NotFoundError()
    target = (entry.dist_dir / file_path).resolve()
    # Guard against path traversal
    if not target.is_relative_to(entry.dist_dir.resolve()):
        raise NotFoundError()
    if not target.exists() or not target.is_file():
        raise NotFoundError()
    return FileResponse(target)
