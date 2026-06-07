from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.util.ip import get_client_ip
from nexctf.model import ScoreAdjustment
from nexctf.module.events import emit
from nexctf.module.scoreboard.cache import invalidate as invalidate_scoreboard
from nexctf.schema.score_adjustment import (
    AdminScoreAdjustmentCreate,
    AdminScoreAdjustmentCreateInternal,
    AdminScoreAdjustmentRead,
    AdminScoreAdjustmentUpdate,
)

score_adjustment_router = APIRouter(
    prefix="/score-adjustment", tags=["Score Adjustment"]
)


@score_adjustment_router.get("")
async def get_score_adjustments(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.ScoreAdjustmentCrud.paginate_params())],
) -> PaginatedResponse[AdminScoreAdjustmentRead]:
    return await crud.ScoreAdjustmentCrud.paginate(
        session=session,
        **params,
        schema=AdminScoreAdjustmentRead,
    )


@score_adjustment_router.post("")
async def create_score_adjustment(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    obj: AdminScoreAdjustmentCreate,
    user: CurrentUserDep,
) -> Response[AdminScoreAdjustmentRead]:
    internal = AdminScoreAdjustmentCreateInternal(
        **obj.model_dump(), created_by_id=user.id
    )
    result = await crud.ScoreAdjustmentCrud.create(
        session=session, obj=internal, schema=AdminScoreAdjustmentRead
    )
    await invalidate_scoreboard(redis, obj.team_id)
    await emit(
        session,
        redis,
        event_type="score_adjustment.created",
        actor_id=user.id,
        ip=get_client_ip(request),
        meta={
            "team_id": str(obj.team_id),
            "amount": obj.amount,
            "reason": obj.reason,
        },
    )
    return result


@score_adjustment_router.get("/{uuid}")
async def get_score_adjustment(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminScoreAdjustmentRead]:
    return await crud.ScoreAdjustmentCrud.get(
        session=session,
        filters=[ScoreAdjustment.id == uuid],
        schema=AdminScoreAdjustmentRead,
    )


@score_adjustment_router.put("/{uuid}")
async def update_score_adjustment(
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    obj: AdminScoreAdjustmentUpdate,
) -> Response[AdminScoreAdjustmentRead]:
    result = await crud.ScoreAdjustmentCrud.update(
        session=session,
        filters=[ScoreAdjustment.id == uuid],
        obj=obj,
        schema=AdminScoreAdjustmentRead,
    )
    if result.data is not None:
        await invalidate_scoreboard(redis, result.data.team_id)
    return result


@score_adjustment_router.delete("/{uuid}")
async def delete_score_adjustment(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    admin: CurrentUserDep,
) -> Response[None]:
    adj = await crud.ScoreAdjustmentCrud.first(
        session=session, filters=[ScoreAdjustment.id == uuid]
    )
    if not adj:
        raise NotFoundError()
    result = await crud.ScoreAdjustmentCrud.delete(
        session=session,
        filters=[ScoreAdjustment.id == uuid],
        return_response=True,
    )
    await invalidate_scoreboard(redis, adj.team_id)
    await emit(
        session,
        redis,
        event_type="score_adjustment.deleted",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={
            "adjustment_id": str(uuid),
            "team_id": str(adj.team_id),
            "amount": adj.amount,
            "reason": adj.reason,
        },
    )
    return result
