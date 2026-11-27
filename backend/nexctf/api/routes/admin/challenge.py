import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_toolsets.exceptions import ConflictError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.api.dep import (
    ChallengeCreateDep,
    ChallengeCtxDep,
    SessionDep,
    validate_body,
)
from nexctf.exceptions import FileNotFoundApiError
from nexctf.model import Challenge, File
from nexctf.module.audit import emit_write
from nexctf.module.challenge.removal import ensure_challenge_removable
from nexctf.plugins.registry import RegistryEntry, challenge_registry
from nexctf.schema.challenge import (
    AdminChallengeFilesUpdate,
    AdminChallengeRead,
    AdminChallengeTypeInfo,
)
from nexctf.schema.file import AdminFileRead
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
        return await entry.crud.create(
            session=session, obj=obj, schema=entry.read_schema
        )
    except IntegrityError:
        raise ConflictError(detail="Challenge title already taken")


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
        return await crud_inst.update(
            session=session,
            filters=[crud_inst.model.id == uuid],
            obj=obj,
            schema=read_schema,
        )
    except IntegrityError:
        raise ConflictError(detail="Challenge title already taken")


@challenge_router.delete("/{uuid}")
async def delete_challenge(
    session: SessionDep,
    uuid: UUID,
    ctx: ChallengeCtxDep,
) -> Response[None]:
    crud_inst, _, _ = ctx
    await ensure_challenge_removable(session, uuid)
    return await crud_inst.delete(
        session=session, filters=[crud_inst.model.id == uuid], return_response=True
    )


async def _challenge_with_files(session: AsyncSession, uuid: UUID) -> Challenge:
    return await crud.ChallengeCrud.get(
        session=session,
        filters=[Challenge.id == uuid],
        load_options=[selectinload(Challenge.files)],
    )


def _file_reads(files: list[File]) -> list[AdminFileRead]:
    return [AdminFileRead.model_validate(f) for f in files]


@challenge_router.get("/{uuid}/files")
async def get_challenge_files(
    session: SessionDep, uuid: UUID
) -> Response[list[AdminFileRead]]:
    """Files attached to the challenge itself, by name."""
    challenge = await _challenge_with_files(session, uuid)
    return Response(data=_file_reads(challenge.files))


@challenge_router.put("/{uuid}/files")
async def set_challenge_files(
    session: SessionDep, uuid: UUID, obj: AdminChallengeFilesUpdate
) -> Response[list[AdminFileRead]]:
    """Replace the challenge's attached files."""
    challenge = await _challenge_with_files(session, uuid)
    wanted = set(obj.file_ids)
    rows = await session.execute(
        select(File).where(File.id.in_(wanted)).order_by(File.name)
    )
    files = list(rows.scalars().all())
    if len(files) != len(wanted):
        raise FileNotFoundApiError()
    before = list(challenge.files)
    challenge.files = files
    await session.flush()
    if {f.id for f in before} != wanted:
        await emit_write(
            session,
            Challenge.__tablename__,
            "updated",
            target_id=challenge.id,
            target_label=challenge.title,
            changes={"files": [[f.name for f in before], [f.name for f in files]]},
        )
    return Response(data=_file_reads(files))
