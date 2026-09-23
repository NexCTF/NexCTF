"""Plugin frontend manifest and static bundle serving."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from nexctf.module import plugin_frontend
from nexctf.schema.plugin import PluginManifestEntry

plugin_router = APIRouter(prefix="/plugins", tags=["Plugins"])


@plugin_router.get("/manifest")
async def get_plugin_manifest() -> list[PluginManifestEntry]:
    return plugin_frontend.manifest(admin=False)


@plugin_router.get("/{plugin_key}/frontend/{file_path:path}", include_in_schema=False)
async def serve_plugin_frontend(
    plugin_key: str, file_path: str, v: str | None = None
) -> FileResponse:
    return plugin_frontend.bundle_response(plugin_key, file_path, v, admin=False)
