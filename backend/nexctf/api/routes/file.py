from uuid import UUID

import nexctf.crud as crud
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from nexctf.api.dep import SessionDep
from nexctf.core import s3
from nexctf.model.file import File

file_router = APIRouter(prefix="/file", tags=["File"])


@file_router.get("/{uuid}/view")
async def view_public_file(session: SessionDep, uuid: UUID) -> RedirectResponse:
    """Redirect to a presigned S3 view URL for a publicly accessible file."""
    file = await crud.FileCrud.get(
        session, filters=[File.id == uuid, File.is_public.is_(True)]
    )
    url = await s3.presigned_view_url(file.s3_key, filename=file.original_filename)
    return RedirectResponse(url=url)
