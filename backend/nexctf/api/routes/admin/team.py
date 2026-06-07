from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_toolsets.exceptions import NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, Response

import nexctf.crud as crud
from nexctf.api.dep import SessionDep
from nexctf.model import CustomFieldValue, Submission, Team
from nexctf.module.stats import compute_admin_team_challenge_stats
from nexctf.schema.custom_field import AdminCustomFieldValueRead
from nexctf.schema.stats import AdminTeamChallengeStats
from nexctf.schema.submission import AdminSubmissionRead
from nexctf.schema.team import (
    AdminTeamCreate,
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
    obj: AdminTeamCreate,
) -> Response[AdminTeamRead]:
    return await crud.TeamCrud.create(session=session, obj=obj, schema=AdminTeamRead)


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
            links=team.links or [],
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
    uuid: UUID,
    obj: AdminTeamUpdate,
) -> Response[AdminTeamRead]:
    return await crud.TeamCrud.update(
        session=session,
        filters=[Team.id == uuid],
        obj=obj,
        schema=AdminTeamRead,
    )


@team_router.delete("/{uuid}")
async def delete_team(session: SessionDep, uuid: UUID) -> Response[None]:
    return await crud.TeamCrud.delete(
        session=session, filters=[Team.id == uuid], return_response=True
    )
