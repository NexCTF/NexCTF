from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.util.ip import get_client_ip
from nexctf.model import Submission
from nexctf.module.events import emit
from nexctf.module.scoreboard.cache import invalidate as invalidate_scoreboard
from nexctf.schema.submission import AdminSubmissionRead

submission_router = APIRouter(prefix="/submission", tags=["Submission"])


@submission_router.get("")
async def get_submissions(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.SubmissionCrud.paginate_params())],
) -> PaginatedResponse[AdminSubmissionRead]:
    return await crud.SubmissionCrud.paginate(
        session=session,
        **params,
        schema=AdminSubmissionRead,
    )


@submission_router.get("/{uuid}")
async def get_submission(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminSubmissionRead]:
    return await crud.SubmissionCrud.get(
        session=session,
        filters=[Submission.id == uuid],
        schema=AdminSubmissionRead,
    )


@submission_router.delete("/{uuid}")
async def delete_submission(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    admin: CurrentUserDep,
) -> Response[None]:
    submission = await crud.SubmissionCrud.first(
        session=session, filters=[Submission.id == uuid]
    )
    if not submission:
        raise NotFoundError()
    team_id = submission.team_id
    result = await crud.SubmissionCrud.delete(
        session=session,
        filters=[Submission.id == uuid],
        return_response=True,
    )
    await invalidate_scoreboard(redis, team_id=team_id)
    await emit(
        session,
        redis,
        event_type="admin.submission_deleted",
        actor_id=admin.id,
        ip=get_client_ip(request),
        meta={
            "submission_id": str(uuid),
            "team_id": str(team_id) if team_id else None,
            "is_correct": submission.is_correct,
            "points_earned": submission.points_earned,
        },
    )
    return result
