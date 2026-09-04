from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response
from sqlalchemy.exc import IntegrityError

from nexctf import crud
from nexctf.api.dep import RedisDep, SessionDep
from nexctf.model import (
    ChallengeFeedback,
    CustomFieldValue,
    ScoreAdjustment,
    Submission,
    Team,
)
from nexctf.module.custom_field import replace_custom_field_values
from nexctf.module.scoreboard.cache import invalidate as invalidate_scoreboard
from nexctf.module.scoreboard.compute import compute_team_score
from nexctf.module.stats import compute_admin_team_challenge_stats
from nexctf.schema.custom_field import AdminCustomFieldValueRead
from nexctf.schema.feedback import AdminFeedbackRead
from nexctf.schema.score_adjustment import AdminScoreAdjustmentRead
from nexctf.schema.scoreboard import PublicTeamScoreDetail
from nexctf.schema.stats import AdminTeamChallengeStats
from nexctf.schema.submission import AdminSubmissionRead
from nexctf.schema.team import (
    AdminTeamCreate,
    AdminTeamCreateRequest,
    AdminTeamDetailRead,
    AdminTeamMember,
    AdminTeamRead,
    AdminTeamUpdate,
)

team_router = APIRouter(prefix="/team", tags=["Team"])


@team_router.get("")
async def get_teams(
    session: SessionDep,
    params: Annotated[dict, Depends(crud.TeamCrud.paginate_params())],
) -> PaginatedResponse[AdminTeamRead]:
    return await crud.TeamCrud.paginate(
        session=session,
        **params,
        schema=AdminTeamRead,
    )


@team_router.post("")
async def create_team(
    session: SessionDep,
    obj: AdminTeamCreateRequest,
) -> Response[AdminTeamRead]:
    try:
        result = await crud.TeamCrud.create(
            session=session,
            obj=AdminTeamCreate(**obj.model_dump(exclude={"custom_fields"})),
            schema=AdminTeamRead,
        )
    except IntegrityError:
        raise ConflictError(detail="Team name already taken")
    if result.data is not None:
        await replace_custom_field_values(
            session, obj.custom_fields, team_id=result.data.id, self_service=False
        )
    return result


@team_router.get("/{uuid}/detail")
async def get_team_detail(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminTeamDetailRead]:
    team = await crud.TeamCrud.first(session=session, filters=[Team.id == uuid])
    if team is None:
        raise NotFoundError()
    cfv_rows = await crud.CustomFieldValueCrud.get_multi(
        session=session, filters=[CustomFieldValue.team_id == uuid]
    )
    return Response(
        data=AdminTeamDetailRead(
            id=team.id,
            name=team.name,
            country=team.country,
            bracket=team.bracket,
            links=team.links or [],
            invite_code=team.invite_code,
            created_at=team.created_at,
            updated_at=team.updated_at,
            users=[AdminTeamMember.model_validate(u) for u in team.users],
            custom_field_values=[
                AdminCustomFieldValueRead.model_validate(cfv) for cfv in cfv_rows
            ],
        )
    )


@team_router.get("/{uuid}/submissions")
async def get_team_submissions(
    session: SessionDep,
    uuid: UUID,
    params: Annotated[dict, Depends(crud.SubmissionCrud.paginate_params())],
) -> PaginatedResponse[AdminSubmissionRead]:
    return await crud.SubmissionCrud.paginate(
        session=session,
        **params,
        filters=[Submission.team_id == uuid],
        schema=AdminSubmissionRead,
    )


@team_router.get("/{uuid}/feedback")
async def get_team_feedbacks(
    session: SessionDep,
    uuid: UUID,
    params: Annotated[dict, Depends(crud.ChallengeFeedbackCrud.paginate_params())],
) -> PaginatedResponse[AdminFeedbackRead]:
    return await crud.ChallengeFeedbackCrud.paginate(
        session=session,
        **params,
        filters=[ChallengeFeedback.team_id == uuid],
        schema=AdminFeedbackRead,
    )


@team_router.get("/{uuid}/score-adjustments")
async def get_team_score_adjustments(
    session: SessionDep,
    uuid: UUID,
    params: Annotated[dict, Depends(crud.ScoreAdjustmentCrud.paginate_params())],
) -> PaginatedResponse[AdminScoreAdjustmentRead]:
    return await crud.ScoreAdjustmentCrud.paginate(
        session=session,
        **params,
        filters=[ScoreAdjustment.team_id == uuid],
        schema=AdminScoreAdjustmentRead,
    )


@team_router.get("/{uuid}/score")
async def get_team_score_detail(
    session: SessionDep,
    uuid: UUID,
) -> Response[PublicTeamScoreDetail]:
    """Score breakdown ignoring ``ctf.freeze_time`` — admins see live numbers."""
    try:
        return Response(data=await compute_team_score(session, uuid))
    except ValueError:
        raise NotFoundError()


@team_router.get("/{uuid}/challenge-stats")
async def get_team_challenge_stats(
    session: SessionDep,
    uuid: UUID,
) -> Response[list[AdminTeamChallengeStats]]:
    stats = await compute_admin_team_challenge_stats(session, uuid)
    return Response(data=stats)


@team_router.get("/{uuid}")
async def get_team(
    session: SessionDep,
    uuid: UUID,
) -> Response[AdminTeamRead]:
    return await crud.TeamCrud.get(
        session=session,
        filters=[Team.id == uuid],
        schema=AdminTeamRead,
    )


@team_router.put("/{uuid}")
async def update_team(
    session: SessionDep,
    redis: RedisDep,
    uuid: UUID,
    obj: AdminTeamUpdate,
) -> Response[AdminTeamRead]:
    try:
        result = await crud.TeamCrud.update(
            session=session,
            filters=[Team.id == uuid],
            obj=obj,
            schema=AdminTeamRead,
        )
    except IntegrityError:
        raise ConflictError(detail="Team name already taken")
    # name/bracket changes affect scoreboard entries; drop this team's cached views
    if obj.name is not None or obj.bracket is not None:
        await invalidate_scoreboard(redis, team_id=uuid)
    return result


@team_router.delete("/{uuid}")
async def delete_team(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.TeamCrud.delete(
        session=session, filters=[Team.id == uuid], return_response=True
    )
