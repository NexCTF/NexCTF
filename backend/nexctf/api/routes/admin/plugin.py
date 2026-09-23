"""Admin plugin registry, admin-only manifest and admin bundle serving."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi_toolsets.schemas import Response

from nexctf.core.appconfig import get_category_meta
from nexctf.module import plugin_frontend
from nexctf.plugins import PluginMeta, get_plugin_metadata
from nexctf.plugins.frontend import frontend_registry
from nexctf.schema.plugin import AdminPluginRead, PluginManifestEntry

plugin_router = APIRouter(prefix="/plugins", tags=["Plugins"])

_OFFICIAL_PLUGINS = frozenset({"nexctf_sandbox", "nexctf_plugin_orchestrator"})


def _is_official(meta: PluginMeta) -> bool:
    return meta.is_builtin or meta.key in _OFFICIAL_PLUGINS


def _read(meta: PluginMeta) -> AdminPluginRead:
    frontend = frontend_registry.get(meta.key)
    return AdminPluginRead(
        key=meta.key,
        name=meta.name,
        display_name=meta.display_name,
        version=meta.version,
        description=meta.description,
        authors=meta.authors,
        repo_url=meta.repo_url,
        homepage_url=meta.homepage_url,
        is_builtin=meta.is_builtin,
        is_active=meta.is_active,
        is_official=_is_official(meta),
        is_disabled=meta.is_disabled,
        has_config=get_category_meta(meta.key).is_plugin,
        missing_bundles=frontend.missing if frontend else [],
        load_error=meta.load_error,
    )


@plugin_router.get("")
async def list_plugins() -> Response[list[AdminPluginRead]]:
    result = [_read(meta) for meta in get_plugin_metadata().values()]
    result.sort(key=lambda p: (not p.is_builtin, p.display_name.lower()))
    return Response(data=result)


@plugin_router.get("/manifest")
async def get_admin_plugin_manifest() -> list[PluginManifestEntry]:
    return plugin_frontend.manifest(admin=True)


@plugin_router.get("/{plugin_key}/frontend/{file_path:path}", include_in_schema=False)
async def serve_admin_plugin_frontend(
    plugin_key: str, file_path: str, v: str | None = None
) -> FileResponse:
    return plugin_frontend.bundle_response(plugin_key, file_path, v, admin=True)
