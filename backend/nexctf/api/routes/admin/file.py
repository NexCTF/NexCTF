import asyncio
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, UploadFile
from nexctf.exceptions import FileNotFoundApiError, NothingToUpdateError
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.core import s3
from nexctf.model.file import File
from nexctf.schema.file import (
    AdminFileCreate,
    AdminFileDetail,
    AdminFileRead,
    AdminFileUpdate,
)

file_router = APIRouter(prefix="/file", tags=["File"])


@file_router.get("")
async def list_files(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.FileCrud.paginate_params())],
) -> PaginatedResponse[AdminFileRead]:
    return await crud.FileCrud.paginate(session=session, **params, schema=AdminFileRead)


@file_router.post("", status_code=201)
async def upload_file(
    session: SessionDep,
    name: Annotated[str, Form()],
    upload: UploadFile,
    is_public: Annotated[bool, Form()] = False,
) -> Response[AdminFileRead]:
    file_id = uuid4()
    s3_key = f"files/{file_id}"

    content = await upload.read()
    await s3.upload(s3_key, content, upload.content_type)

    return await crud.FileCrud.create(
        session=session,
        obj=AdminFileCreate(
            id=file_id,
            name=name,
            s3_key=s3_key,
            original_filename=upload.filename or name,
            mime_type=upload.content_type,
            file_size=len(content),
            is_public=is_public,
        ),
        schema=AdminFileRead,
    )


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

        content = await upload.read()
        await s3.upload(file_read.s3_key, content, upload.content_type)

        updates["original_filename"] = upload.filename or file_read.original_filename
        updates["mime_type"] = upload.content_type
        updates["file_size"] = len(content)

    return await crud.FileCrud.update(
        session=session,
        filters=[File.id == uuid],
        obj=AdminFileUpdate(**updates),
        schema=AdminFileRead,
    )


@file_router.delete("/{uuid}")
async def delete_file(session: SessionDep, uuid: UUID) -> Response[None]:
    file = await crud.FileCrud.get(session=session, filters=[File.id == uuid])

    await s3.delete(file.s3_key)
    return await crud.FileCrud.delete(
        session=session, filters=[File.id == uuid], return_response=True
    )
