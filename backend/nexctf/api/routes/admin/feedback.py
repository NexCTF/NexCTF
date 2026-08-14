"""Admin challenge-feedback listing."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_toolsets.schemas import PaginatedResponse

from nexctf import crud
from nexctf.api.dep import SessionDep
from nexctf.schema.feedback import AdminFeedbackRead

feedback_router = APIRouter(prefix="/feedback", tags=["Feedback"])


@feedback_router.get("")
async def get_feedbacks(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.ChallengeFeedbackCrud.paginate_params())],
) -> PaginatedResponse[AdminFeedbackRead]:
    return await crud.ChallengeFeedbackCrud.paginate(
        session=session,
        **params,
        schema=AdminFeedbackRead,
    )
