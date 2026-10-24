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
from nexctf.core.eventbus import publish_event
from nexctf.exceptions import ConfigValidationError
from nexctf.module.audit import REDACTED, audit_actor, redact
from nexctf.module.events import emit
from nexctf.module.info import invalidate as invalidate_info
from nexctf.module.scoreboard import invalidate as invalidate_scoreboard
from nexctf.module.stats import invalidate_team
from nexctf.schema.config import AdminConfigBulkUpdate, AdminConfigRead
from nexctf.util.datetime import EVENT_TIME_KEYS, event_time_errors

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
    errors: list[str] = []
    staged: dict[str, str] = {}

    for key, value in obj.items.items():
        if key not in appconfig.all_defs():
            errors.append(f"Unknown key: {key!r}")
            continue
        if (
            value == REDACTED
            and appconfig.get_def(key).type == appconfig.ConfigType.SECRET
        ):
            continue
        try:
            await appconfig.stage(session, key, value)
            staged[key] = value
        except ValueError as e:
            errors.append(f"{key}: {e}")

    overrides = {**old_overrides, **staged}
    if not errors and staged.keys() & EVENT_TIME_KEYS:
        errors = event_time_errors(overrides)
    if errors:
        raise ConfigValidationError(errors)

    await appconfig.commit_and_store(session, redis, staged)
    await invalidate_info(redis)
    if staged.keys() & {"ctf.freeze_time", "ctf.end_time"}:
        await invalidate_scoreboard(redis)
        await invalidate_team(redis)
    await publish_event(redis, ["config:update"], "1")

    if staged:
        actor_id, ip = audit_actor()
        changes = {
            key: [
                redact(key, appconfig.get_with_overrides(key, old_overrides)),
                redact(key, appconfig.get_with_overrides(key, overrides)),
            ]
            for key in sorted(staged)
        }
        await emit(
            session,
            redis,
            event_type="config.updated",
            actor_id=actor_id,
            ip=ip,
            meta={"changes": changes},
        )

    return Response(data=[_build_item(k, overrides) for k in appconfig.all_defs()])
