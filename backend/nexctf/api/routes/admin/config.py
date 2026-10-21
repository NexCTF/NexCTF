from typing import cast

from fastapi import APIRouter, Request
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import (
    ConfigDep,
    RedisDep,
    SessionDep,
    TokenScopesDep,
    require_fresh_unless_token,
)
from nexctf.core import appconfig
from nexctf.module.audit import REDACTED
from nexctf.module.config import save_config
from nexctf.schema.config import AdminConfigBulkUpdate, AdminConfigRead

config_router = APIRouter(prefix="/config", tags=["Config"])


def _build_item(key: str, overrides: dict[str, str]) -> AdminConfigRead:
    def_ = appconfig.get_def(key)
    value = appconfig.get_with_overrides(key, overrides)
    if def_.type == appconfig.ConfigType.SECRET and value:
        value = REDACTED
    return AdminConfigRead(
        key=def_.key,
        type=cast(appconfig.ConfigType, def_.type).value,
        value=value,
        default=cast(str, def_.default),
        label=def_.label,
        description=def_.description,
        choices=def_.choices,
        min=def_.min,
        max=def_.max,
        category=def_.category,
        category_label=appconfig.get_category_meta(def_.category).label,
        category_icon=appconfig.get_category_meta(def_.category).icon,
        category_section=appconfig.get_category_meta(def_.category).section,
        is_plugin_category=appconfig.get_category_meta(def_.category).is_plugin,
    )


@config_router.get("")
async def list_config(overrides: ConfigDep) -> Response[list[AdminConfigRead]]:
    return Response(data=[_build_item(k, overrides) for k in appconfig.all_defs()])


@config_router.put("")
async def bulk_update_config(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    old_overrides: ConfigDep,
    obj: AdminConfigBulkUpdate,
    granted: TokenScopesDep,
) -> Response[list[AdminConfigRead]]:
    """Save config; from a browser, auth-related keys need a fresh session."""
    defs = appconfig.all_defs()
    if any(key in defs and defs[key].reauth for key in obj.items):
        require_fresh_unless_token(request, granted)
    overrides = await save_config(session, redis, obj.items, old_overrides)
    return Response(data=[_build_item(k, overrides) for k in appconfig.all_defs()])
