from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy import Row, select

from nexctf import crud
from nexctf.api.dep import RedisDep, SessionDep
from nexctf.model import Question
from nexctf.module.challenge.removal import ensure_question_removable
from nexctf.module.submission import recalculate_question
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
        filters=[Question.id == uuid],
        schema=AdminQuestionRead,
    )


def _trap_set(flags: list[str] | None) -> set[str]:
    return {f.casefold() for f in flags or ()}


def _scoring_changed(before: Row, obj: AdminQuestionUpdate) -> bool:
    """Whether *obj* changes how the question's submissions are scored."""
    fields = obj.model_fields_set
    return (
        (
            obj.trap_flags is not None
            and _trap_set(obj.trap_flags) != _trap_set(before.trap_flags)
        )
        or (obj.points is not None and obj.points != before.points)
        or ("malus" in fields and obj.malus != before.malus)
    )


@question_router.put("/{uuid}")
async def update_question(
    session: SessionDep, redis: RedisDep, uuid: UUID, obj: AdminQuestionUpdate
) -> Response[AdminQuestionRead]:
    before = (
        await session.execute(
            select(Question.trap_flags, Question.points, Question.malus).where(
                Question.id == uuid
            )
        )
    ).one_or_none()
    result = await crud.QuestionCrud.update(
        session=session,
        filters=[Question.id == uuid],
        obj=obj,
        schema=AdminQuestionRead,
    )
    if before is not None and _scoring_changed(before, obj):
        await recalculate_question(session, redis, uuid)
    return result


@question_router.delete("/{uuid}")
async def delete_question(session: SessionDep, uuid: UUID) -> Response[None]:
    await ensure_question_removable(session, uuid)
    return await crud.QuestionCrud.delete(
        session=session,
        filters=[Question.id == uuid],
        return_response=True,
    )
