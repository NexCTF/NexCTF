from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.schema.question import (
    AdminQuestionCreate,
    AdminQuestionRead,
    AdminQuestionUpdate,
)

question_router = APIRouter(prefix="/question", tags=["Question"])


@question_router.get("")
async def get_questions(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.QuestionCrud.paginate_params())],
) -> PaginatedResponse[AdminQuestionRead]:
    return await crud.QuestionCrud.paginate(
        session=session, **params, schema=AdminQuestionRead
    )


@question_router.post("")
async def create_question(
    session: SessionDep,
    obj: AdminQuestionCreate,
) -> Response[AdminQuestionRead]:
    return await crud.QuestionCrud.create(
        session=session, obj=obj, schema=AdminQuestionRead
    )


@question_router.get("/{uuid}")
async def get_question(session: SessionDep, uuid: UUID) -> Response[AdminQuestionRead]:
    return await crud.QuestionCrud.get(
        session=session,
        filters=[crud.QuestionCrud.model.id == uuid],
        schema=AdminQuestionRead,
    )


@question_router.put("/{uuid}")
async def update_question(
    session: SessionDep, uuid: UUID, obj: AdminQuestionUpdate
) -> Response[AdminQuestionRead]:
    return await crud.QuestionCrud.update(
        session=session,
        filters=[crud.QuestionCrud.model.id == uuid],
        obj=obj,
        schema=AdminQuestionRead,
    )


@question_router.delete("/{uuid}")
async def delete_question(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.QuestionCrud.delete(
        session=session,
        filters=[crud.QuestionCrud.model.id == uuid],
        return_response=True,
    )
