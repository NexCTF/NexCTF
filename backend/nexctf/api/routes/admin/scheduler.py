import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.orm import joinedload, selectinload

import nexctf.crud as crud
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.model.scheduler import SchedulerJob
from nexctf.module.scheduler import force_run_job
from nexctf.plugins.registry import SchedulerEntry, scheduler_registry
from nexctf.util.pydantic import resolve_dynamic_defaults
from nexctf.schema.scheduler import (
    AdminSchedulerJobCreate,
    AdminSchedulerJobCreateInternal,
    AdminSchedulerJobRead,
    AdminSchedulerJobReadDetail,
    AdminSchedulerJobTypeRead,
    AdminSchedulerJobUpdate,
    AdminSchedulerTaskRead,
)

scheduler_router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


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
) -> Response[AdminSchedulerJobRead]:
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
) -> Response[AdminSchedulerJobReadDetail]:
    return await crud.SchedulerJobCrud.get(
        session,
        filters=[SchedulerJob.id == uuid],
        load_options=[
            joinedload(SchedulerJob.created_by),
            selectinload(SchedulerJob.tasks),
        ],
        schema=AdminSchedulerJobReadDetail,
    )


@scheduler_router.put("/jobs/{uuid}")
async def update_job(
    session: SessionDep,
    uuid: UUID,
    obj: AdminSchedulerJobUpdate,
) -> Response[AdminSchedulerJobRead]:
    if obj.params is not None:
        job = await crud.SchedulerJobCrud.get(
            session, filters=[SchedulerJob.id == uuid]
        )
        try:
            entry = scheduler_registry.get(job.job_type)
        except KeyError:
            raise NotFoundError(detail=f"Unregistered job type: {job.job_type!r}")
        entry.update_schema.model_validate(obj.params)

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


@scheduler_router.get("/tasks")
async def get_tasks(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.SchedulerTaskCrud.paginate_params())],
) -> PaginatedResponse[AdminSchedulerTaskRead]:
    return await crud.SchedulerTaskCrud.paginate(
        session=session,
        **params,
        schema=AdminSchedulerTaskRead,
    )
