import asyncio
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy import ColumnElement, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud
from nexctf.api.dep import SessionDep, TokenScopesDep
from nexctf.api.scope import group_for_path
from nexctf.core import s3
from nexctf.core.config import settings
from nexctf.enums import FileUsageFilter, FileUsageKind
from nexctf.exceptions import (
    FileInUseError,
    FileNotFoundApiError,
    NothingToUpdateError,
)
from nexctf.model.file import File
from nexctf.module import file_usage
from nexctf.module.audit import REDACTED
from nexctf.schema.file import (
    AdminFileCreate,
    AdminFileDetail,
    AdminFileListItem,
    AdminFileRead,
    AdminFileSummary,
    AdminFileUpdate,
    AdminFileUploadRead,
    FileUsage,
)
from nexctf.util.upload import checked_size, sha256_of

file_router = APIRouter(prefix="/file", tags=["File"])

_KIND_PATHS = {
    FileUsageKind.PAGE_TEXT: "/admin/page",
    FileUsageKind.NOTIFICATION_TEXT: "/admin/notification",
    FileUsageKind.CONFIG: "/admin/config",
}


def _visible(usage: FileUsage, granted: frozenset[str]) -> bool:
    path = _KIND_PATHS.get(usage.kind)
    if path is None:
        return True
    return f"read:{group_for_path(settings.API_V1_STR + path)}" in granted


def redacted(found: list[FileUsage], granted: frozenset[str] | None) -> list[FileUsage]:
    """*found*, with the targets a token's scopes do not reach blanked out."""
    if granted is None:
        return found
    return [
        u if _visible(u, granted) else FileUsage(kind=u.kind, label=REDACTED)
        for u in found
    ]


def _list_filters(
    texts: file_usage.Usages,
    usage: list[FileUsageFilter],
    challenge_id: UUID | None,
    mime_prefix: str | None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if mime_prefix:
        filters.append(File.mime_type.startswith(mime_prefix, autoescape=True))
    if len(set(usage)) == 1:
        used = file_usage.used_clause(list(texts))
        filters.append(used if usage[0] is FileUsageFilter.USED else not_(used))
    if challenge_id is not None:
        filters.append(file_usage.challenge_clause(challenge_id, texts))
    return filters


@file_router.get("")
async def list_files(
    session: SessionDep,
    granted: TokenScopesDep,
    params: Annotated[dict, Depends(crud.FileCrud.paginate_params())],
    usage: Annotated[list[FileUsageFilter] | None, Query()] = None,
    challenge_id: Annotated[UUID | None, Query()] = None,
    mime_prefix: Annotated[str | None, Query(max_length=128)] = None,
) -> PaginatedResponse[AdminFileListItem]:
    """Stored files with where each one is used."""
    texts = await file_usage.text_usages(session)
    result = await crud.FileCrud.paginate(
        session=session,
        **params,
        filters=_list_filters(texts, usage or [], challenge_id, mime_prefix),
        schema=AdminFileListItem,
    )
    found = await file_usage.usages(session, [f.id for f in result.data], texts)
    for item in result.data:
        item.usages = redacted(found[item.id], granted)
    if result.filter_attributes is not None:
        result.filter_attributes["usage"] = [f.value for f in FileUsageFilter]
    return result


@file_router.get("/summary")
async def get_files_summary(session: SessionDep) -> Response[AdminFileSummary]:
    """File count, total size and unused count."""
    return Response(data=await file_usage.summary(session))


async def _duplicates(
    session: AsyncSession, sha256: str, file_id: UUID
) -> list[AdminFileRead]:
    rows = await session.execute(
        select(File).where(File.sha256 == sha256, File.id != file_id)
    )
    return [AdminFileRead.model_validate(f) for f in rows.scalars().all()]


@file_router.post("", status_code=201)
async def upload_file(
    session: SessionDep,
    name: Annotated[str, Form()],
    upload: UploadFile,
    is_public: Annotated[bool, Form()] = False,
) -> Response[AdminFileUploadRead]:
    file_id = uuid4()
    s3_key = f"files/{file_id}"

    size = checked_size(upload)
    sha256 = await sha256_of(upload)
    await s3.upload_stream(s3_key, upload.file, upload.content_type)

    instance = await crud.FileCrud.create(
        session=session,
        obj=AdminFileCreate(
            id=file_id,
            name=name,
            s3_key=s3_key,
            original_filename=upload.filename or name,
            mime_type=upload.content_type,
            file_size=size,
            is_public=is_public,
            sha256=sha256,
        ),
    )
    read = AdminFileUploadRead.model_validate(instance)
    read.duplicates = await _duplicates(session, sha256, file_id)
    return Response(data=read)


@file_router.get("/{uuid}")
async def get_file(session: SessionDep, uuid: UUID) -> Response[AdminFileDetail]:
    result = await crud.FileCrud.get(
        session=session, filters=[File.id == uuid], schema=AdminFileRead
    )
    if result.data is None:
        raise FileNotFoundApiError()
    file_read = result.data
    view_url, download_url = await asyncio.gather(
        s3.presigned_view_url(file_read.s3_key, filename=file_read.original_filename),
        s3.presigned_download_url(file_read.s3_key, file_read.original_filename),
    )
    return Response(
        data=AdminFileDetail(
            **file_read.model_dump(), view_url=view_url, download_url=download_url
        )
    )


@file_router.put("/{uuid}")
async def update_file(
    session: SessionDep,
    uuid: UUID,
    name: Annotated[str | None, Form()] = None,
    upload: UploadFile | None = None,
    is_public: Annotated[bool | None, Form()] = None,
) -> Response[AdminFileRead]:
    if name is None and upload is None and is_public is None:
        raise NothingToUpdateError()

    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name
    if is_public is not None:
        updates["is_public"] = is_public

    if upload is not None:
        result = await crud.FileCrud.get(
            session=session, filters=[File.id == uuid], schema=AdminFileRead
        )
        if result.data is None:
            raise FileNotFoundApiError()
        file_read = result.data

        size = checked_size(upload)
        updates["sha256"] = await sha256_of(upload)
        await s3.upload_stream(file_read.s3_key, upload.file, upload.content_type)

        updates["original_filename"] = upload.filename or file_read.original_filename
        updates["mime_type"] = upload.content_type
        updates["file_size"] = size

    return await crud.FileCrud.update(
        session=session,
        filters=[File.id == uuid],
        obj=AdminFileUpdate(**updates),
        schema=AdminFileRead,
    )


@file_router.delete("/{uuid}")
async def delete_file(
    session: SessionDep,
    granted: TokenScopesDep,
    uuid: UUID,
    force: Annotated[bool, Query()] = False,
) -> Response[None]:
    file = await crud.FileCrud.get(session=session, filters=[File.id == uuid])
    s3_key = file.s3_key
    if not force:
        texts = await file_usage.text_usages(session, uuid)
        found = (await file_usage.usages(session, [uuid], texts))[uuid]
        if found:
            shown = redacted(found, granted)
            raise FileInUseError(data=[u.model_dump(mode="json") for u in shown])

    response = await crud.FileCrud.delete(
        session=session, filters=[File.id == uuid], return_response=True
    )
    await session.flush()
    await s3.delete(s3_key)
    return response
