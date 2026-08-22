import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response

from nexctf import crud
from nexctf.api.dep import ConfigDep, CurrentUserDep, RedisDep, SessionDep
from nexctf.model.scheduler import SchedulerJob, SchedulerTask
from nexctf.module.scheduler import force_run_job
from nexctf.plugins.registry import SchedulerEntry, scheduler_registry
from nexctf.schema.scheduler import (
    AdminSchedulerJobCreate,
    AdminSchedulerJobCreateInternal,
    AdminSchedulerJobRead,
    AdminSchedulerJobTypeRead,
    AdminSchedulerJobUpdate,
    AdminSchedulerTaskRead,
    CronExpression,
    CronPreview,
)
from nexctf.util.cron import next_fire, next_fires
from nexctf.util.datetime import event_timezone
from nexctf.util.pydantic import resolve_dynamic_defaults

scheduler_router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

_PREVIEW_RUNS = 3


@scheduler_router.get("/cron/next")
async def get_cron_next(
    overrides: ConfigDep,
    expr: CronExpression,
) -> Response[CronPreview]:
    """Preview the next fire times of a cron expression, in UTC."""
    tz = event_timezone(overrides)
    return Response(
        data=CronPreview(
            timezone=tz,
            next_runs=next_fires(expr, datetime.now(UTC), count=_PREVIEW_RUNS, tz=tz),
        )
    )


@scheduler_router.get("/jobs/types")
async def get_job_types() -> Response[list[AdminSchedulerJobTypeRead]]:
    async def _resolve(name: str, entry: SchedulerEntry) -> AdminSchedulerJobTypeRead:
        if entry.create_schema is entry.update_schema:
            resolved = await resolve_dynamic_defaults(entry.create_schema)
            create = update = resolved
        else:
            create, update = await asyncio.gather(
                resolve_dynamic_defaults(entry.create_schema),
                resolve_dynamic_defaults(entry.update_schema),
            )
        return AdminSchedulerJobTypeRead(
            type_name=name, create_schema=create, update_schema=update
        )

    return Response(
        data=list(
            await asyncio.gather(
                *[_resolve(name, entry) for name, entry in scheduler_registry.items()]
            )
        )
    )


@scheduler_router.get("/jobs")
async def get_jobs(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.SchedulerJobCrud.paginate_params())],
) -> PaginatedResponse[AdminSchedulerJobRead]:
    return await crud.SchedulerJobCrud.paginate(
        session=session,
        **params,
        schema=AdminSchedulerJobRead,
    )


@scheduler_router.post("/jobs")
async def create_job(
    session: SessionDep,
    obj: AdminSchedulerJobCreate,
    user: CurrentUserDep,
    overrides: ConfigDep,
) -> Response[AdminSchedulerJobRead]:
    if obj.scheduled_at is None and obj.cron_expression:
        obj.scheduled_at = next_fire(
            obj.cron_expression, datetime.now(UTC), event_timezone(overrides)
        )

    try:
        entry = scheduler_registry.get(obj.job_type)
    except KeyError:
        raise NotFoundError(detail=f"Unknown job type: {obj.job_type!r}")

    entry.create_schema.model_validate(obj.params)

    internal = AdminSchedulerJobCreateInternal(
        **obj.model_dump(), created_by_id=user.id
    )
    return await crud.SchedulerJobCrud.create(
        session=session, obj=internal, schema=AdminSchedulerJobRead
    )


@scheduler_router.get("/jobs/{uuid}")
async def get_job(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminSchedulerJobRead]:
    return await crud.SchedulerJobCrud.get(
        session,
        filters=[SchedulerJob.id == uuid],
        schema=AdminSchedulerJobRead,
    )


@scheduler_router.put("/jobs/{uuid}")
async def update_job(
    session: SessionDep,
    uuid: UUID,
    obj: AdminSchedulerJobUpdate,
    overrides: ConfigDep,
) -> Response[AdminSchedulerJobRead]:
    if obj.params is not None or obj.cron_expression is not None:
        job = await crud.SchedulerJobCrud.get(
            session, filters=[SchedulerJob.id == uuid]
        )
        if obj.params is not None:
            try:
                entry = scheduler_registry.get(job.job_type)
            except KeyError:
                raise NotFoundError(detail=f"Unregistered job type: {job.job_type!r}")
            entry.update_schema.model_validate(obj.params)
        if obj.cron_expression and obj.cron_expression != job.cron_expression:
            obj.scheduled_at = next_fire(
                obj.cron_expression, datetime.now(UTC), event_timezone(overrides)
            )

    return await crud.SchedulerJobCrud.update(
        session=session,
        filters=[SchedulerJob.id == uuid],
        obj=obj,
        schema=AdminSchedulerJobRead,
    )


@scheduler_router.delete("/jobs/{uuid}")
async def delete_job(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.SchedulerJobCrud.delete(
        session=session,
        filters=[SchedulerJob.id == uuid],
        return_response=True,
    )


@scheduler_router.post("/jobs/{uuid}/run")
async def run_job(
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
) -> Response[AdminSchedulerTaskRead]:
    job = await crud.SchedulerJobCrud.get(session, filters=[SchedulerJob.id == uuid])
    task = await force_run_job(job, session, redis)
    return Response(data=AdminSchedulerTaskRead.model_validate(task))


@scheduler_router.get("/jobs/{uuid}/tasks")
async def get_job_tasks(
    session: SessionDep,
    uuid: UUID,
    params: Annotated[
        dict,
        Depends(
            crud.SchedulerTaskCrud.paginate_params(
                default_order_field=SchedulerTask.started_at, default_order="desc"
            )
        ),
    ],
) -> PaginatedResponse[AdminSchedulerTaskRead]:
    """Execution history for one job, newest first."""
    return await crud.SchedulerTaskCrud.paginate(
        session=session,
        **params,
        filters=[SchedulerTask.job_id == uuid],
        schema=AdminSchedulerTaskRead,
    )
