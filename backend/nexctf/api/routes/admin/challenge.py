import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_toolsets.exceptions import ConflictError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

from nexctf import crud
from nexctf.api.dep import (
    ChallengeCreateDep,
    ChallengeCtxDep,
    SessionDep,
    validate_body,
)
from nexctf.module.challenge import lifecycle
from nexctf.plugins.registry import RegistryEntry, challenge_registry
from nexctf.schema.challenge import AdminChallengeRead, AdminChallengeTypeInfo
from nexctf.util.pydantic import resolve_dynamic_defaults

challenge_router = APIRouter(prefix="/challenge", tags=["Challenge"])


@challenge_router.get("/types")
async def get_challenge_types() -> Response[list[AdminChallengeTypeInfo]]:
    async def _resolve(name: str, e: RegistryEntry) -> AdminChallengeTypeInfo:
        create, update = await asyncio.gather(
            resolve_dynamic_defaults(e.create_schema),
            resolve_dynamic_defaults(e.update_schema),
        )
        return AdminChallengeTypeInfo(
            type_name=name,
            create_schema=create,
            update_schema=update,
            read_schema=e.read_schema.model_json_schema(),
        )

    return Response(
        data=list(
            await asyncio.gather(
                *[_resolve(name, e) for name, e in challenge_registry.items()]
            )
        )
    )


@challenge_router.get("")
async def get_challenges(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.ChallengeCrud.paginate_params())],
) -> PaginatedResponse[AdminChallengeRead]:
    return await crud.ChallengeCrud.paginate(
        session=session,
        **params,
        schema=AdminChallengeRead,
    )


@challenge_router.post("/{challenge_type}", response_model=Response[Any])
async def create_challenge(
    session: SessionDep,
    obj: ChallengeCreateDep,
    challenge_type: str,
):
    entry = challenge_registry.get(challenge_type)
    try:
        challenge = await lifecycle.create(session, entry, obj)
    except IntegrityError:
        raise ConflictError(detail="Challenge title already taken")
    return Response(data=entry.read_schema.model_validate(challenge))


@challenge_router.get("/{uuid}", response_model=Response[Any])
async def get_challenge(
    session: SessionDep,
    ctx: ChallengeCtxDep,
    uuid: UUID,
):
    crud_inst, _, read_schema = ctx
    return await crud_inst.get(
        session=session, filters=[crud_inst.model.id == uuid], schema=read_schema
    )


@challenge_router.put("/{uuid}", response_model=Response[Any])
async def update_challenge(
    session: SessionDep,
    uuid: UUID,
    request: Request,
    ctx: ChallengeCtxDep,
):
    crud_inst, update_schema, read_schema = ctx
    obj = await validate_body(update_schema, request)
    try:
        challenge = await lifecycle.update(session, crud_inst, obj, uuid)
    except IntegrityError:
        raise ConflictError(detail="Challenge title already taken")
    return Response(data=read_schema.model_validate(challenge))


@challenge_router.delete("/{uuid}")
async def delete_challenge(
    session: SessionDep,
    uuid: UUID,
    ctx: ChallengeCtxDep,
) -> Response[None]:
    crud_inst, _, _ = ctx
    await lifecycle.delete(session, crud_inst, uuid)
    return Response(data=None)
