"""Admin plugin registry endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi_toolsets.schemas import Response

from nexctf.plugins import get_plugin_metadata
from nexctf.schema.plugin import AdminPluginRead

plugin_router = APIRouter(prefix="/plugins", tags=["Plugins"])

_OFFICIAL_PREFIX = "https://github.com/NexCTF/"


def _is_official(repo_url: str | None) -> bool:
    return bool(repo_url and repo_url.startswith(_OFFICIAL_PREFIX))


@plugin_router.get("")
async def list_plugins() -> Response[list[AdminPluginRead]]:
    result = [
        AdminPluginRead(
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
            is_official=_is_official(meta.repo_url),
            load_error=meta.load_error,
        )
        for meta in get_plugin_metadata().values()
    ]
    result.sort(key=lambda p: (not p.is_builtin, p.display_name.lower()))
    return Response(data=result)
