import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import (
    RedisDep,
    SessionDep,
    SolutionCreateDep,
    SolutionCtxDep,
    validate_body,
)
from nexctf.enums import InputType
from nexctf.module.submission import recalculate_question
from nexctf.plugins.registry import RegistryEntry, solution_registry
from nexctf.schema.solution import AdminSolutionRead, AdminSolutionTypeInfo
from nexctf.util.pydantic import resolve_dynamic_defaults

solution_router = APIRouter(prefix="/solution", tags=["Solution"])


@solution_router.get("/types")
async def get_solution_types(
    input_type: InputType | None = Query(default=None),
) -> Response[list[AdminSolutionTypeInfo]]:
    async def _resolve(name: str, e: RegistryEntry) -> AdminSolutionTypeInfo:
        create, update, read = await asyncio.gather(
            resolve_dynamic_defaults(e.create_schema),
            resolve_dynamic_defaults(e.update_schema),
            resolve_dynamic_defaults(e.read_schema),
        )
        return AdminSolutionTypeInfo(
            type_name=name,
            description=e.description,
            create_schema=create,
            update_schema=update,
            read_schema=read,
            compatible_input_types=[t.value for t in e.compatible_input_types]
            if e.compatible_input_types is not None
            else None,
        )

    entries = (
        solution_registry.compatible_with(input_type).items()
        if input_type is not None
        else solution_registry.items()
    )
    return Response(
        data=list(await asyncio.gather(*[_resolve(name, e) for name, e in entries]))
    )


@solution_router.get("")
async def get_solutions(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.SolutionCrud.paginate_params())],
) -> PaginatedResponse[AdminSolutionRead]:
    return await crud.SolutionCrud.paginate(
        session=session,
        **params,
        schema=AdminSolutionRead,
    )


@solution_router.post("/{solve_type}", response_model=Response[Any])
async def create_solution(
    session: SessionDep,
    redis: RedisDep,
    obj: SolutionCreateDep,
    solve_type: str,
):
    entry = solution_registry.get(solve_type)
    result = await entry.crud.create(session=session, obj=obj, schema=entry.read_schema)
    question_id: UUID = obj.model_dump()["question_id"]
    await recalculate_question(session, redis, question_id)
    return result


@solution_router.get("/{uuid}", response_model=Response[Any])
async def get_solution(
    session: SessionDep,
    ctx: SolutionCtxDep,
    uuid: UUID,
):
    crud_inst, _, read_schema, _ = ctx
    return await crud_inst.get(
        session=session, filters=[crud_inst.model.id == uuid], schema=read_schema
    )


@solution_router.put("/{uuid}", response_model=Response[Any])
async def update_solution(
    session: SessionDep,
    redis: RedisDep,
    ctx: SolutionCtxDep,
    request: Request,
    uuid: UUID,
):
    crud_inst, update_schema, read_schema, question_id = ctx
    obj = await validate_body(update_schema, request)
    result = await crud_inst.update(
        session=session,
        filters=[crud_inst.model.id == uuid],
        obj=obj,
        schema=read_schema,
    )
    if question_id is not None:
        await recalculate_question(session, redis, question_id)
    return result


@solution_router.delete("/{uuid}")
async def delete_solution(
    session: SessionDep,
    redis: RedisDep,
    ctx: SolutionCtxDep,
    uuid: UUID,
) -> Response[None]:
    crud_inst, _, _, question_id = ctx
    result = await crud_inst.delete(
        session=session, filters=[crud_inst.model.id == uuid], return_response=True
    )
    if question_id is not None:
        await recalculate_question(session, redis, question_id)
    return result
