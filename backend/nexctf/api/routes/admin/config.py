from typing import cast

from fastapi import APIRouter
from nexctf.exceptions import ConfigValidationError
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import RedisDep, SessionDep
from nexctf.core import appconfig
from nexctf.module.audit import audit_actor, redact
from nexctf.module.events import emit
from nexctf.module.scoreboard import invalidate as invalidate_scoreboard
from nexctf.schema.config import AdminConfigBulkUpdate, AdminConfigRead

config_router = APIRouter(prefix="/config", tags=["Config"])


def _build_item(key: str, overrides: dict[str, str]) -> AdminConfigRead:
    def_ = appconfig.get_def(key)
    return AdminConfigRead(
        key=def_.key,
        type=cast(appconfig.ConfigType, def_.type).value,
        value=appconfig.get_with_overrides(key, overrides),
        default=cast(str, def_.default),
        label=def_.label,
        description=def_.description,
        choices=def_.choices,
        category=def_.category,
        category_label=appconfig.get_category_meta(def_.category).label,
        category_icon=appconfig.get_category_meta(def_.category).icon,
        category_section=appconfig.get_category_meta(def_.category).section,
        is_plugin_category=appconfig.get_category_meta(def_.category).is_plugin,
    )


@config_router.get("")
async def list_config(redis: RedisDep) -> Response[list[AdminConfigRead]]:
    overrides = await appconfig.fetch_overrides(redis)
    return Response(data=[_build_item(k, overrides) for k in appconfig.all_defs()])


@config_router.put("")
async def bulk_update_config(
    session: SessionDep,
    redis: RedisDep,
    obj: AdminConfigBulkUpdate,
) -> Response[list[AdminConfigRead]]:
    errors: list[str] = []
    staged: dict[str, str] = {}
    old_overrides = await appconfig.fetch_overrides(redis)

    for key, value in obj.items.items():
        if key not in appconfig.all_defs():
            errors.append(f"Unknown key: {key!r}")
            continue
        try:
            await appconfig.stage(session, key, value)
            staged[key] = value
        except ValueError as e:
            errors.append(f"{key}: {e}")

    if errors:
        raise ConfigValidationError(errors)

    await appconfig.commit_and_cache(session, redis, staged)
    await redis.publish("config:update", "1")

    overrides = await appconfig.fetch_overrides(redis)

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

    if "ctf.freeze_time" in staged:
        await invalidate_scoreboard(redis)

    return Response(data=[_build_item(k, overrides) for k in appconfig.all_defs()])
