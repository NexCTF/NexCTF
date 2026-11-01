from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi import Response as FastAPIResponse
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import BracketDep, ConfigDep, RedisDep, SessionDep
from nexctf.module.audit import audit_actor
from nexctf.module.events import emit
from nexctf.module.scoreboard import export
from nexctf.module.scoreboard.cache import get_admin_scoreboard, invalidate
from nexctf.schema import AdminScoreboard

scoreboard_router = APIRouter(prefix="/scoreboard", tags=["Admin Scoreboard"])


@scoreboard_router.get("")
async def get_admin_scoreboard_endpoint(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    bracket: BracketDep = None,
) -> Response[AdminScoreboard]:
    result = await get_admin_scoreboard(
        session, redis, overrides=overrides, bracket=bracket
    )
    return Response(data=result)


@scoreboard_router.get("/export")
async def export_admin_scoreboard(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    fmt: Annotated[
        export.ExportFormat, Query(alias="format")
    ] = export.ExportFormat.csv,
    columns: Annotated[list[str] | None, Query()] = None,
    bracket: BracketDep = None,
) -> FastAPIResponse:
    """Download the scoreboard as CSV (selectable columns), JSON or CTFtime JSON."""
    board = await get_admin_scoreboard(
        session, redis, overrides=overrides, bracket=bracket
    )
    content, media_type = export.render(board, fmt, columns or ())
    filename = export.filename_for(fmt, datetime.now(UTC), bracket)
    actor_id, ip = audit_actor()
    await emit(
        session,
        redis,
        event_type="scoreboard.exported",
        actor_id=actor_id,
        ip=ip,
        target_type="scoreboard",
        target_label=filename,
        meta={"format": fmt.value, "bracket": bracket, "columns": columns or []},
    )
    return FastAPIResponse(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@scoreboard_router.post("/invalidate")
async def invalidate_scoreboard_cache(
    redis: RedisDep,
    team_id: UUID | None = None,
) -> Response[None]:
    await invalidate(redis, team_id=team_id)
    return Response(data=None)
