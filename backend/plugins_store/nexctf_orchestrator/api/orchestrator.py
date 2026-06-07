from uuid import UUID

from fastapi import APIRouter, Security
from fastapi_toolsets.schemas import Response

from nexctf.api.dep import SessionDep
from nexctf.api.security import auth
from nexctf.exceptions import NoTeamError
from nexctf.model import User
from nexctf.plugins.registry import challenge_registry

from ..module.fake_orchestrator import FakeOrchestrator
from ..schema import PublicOrchestratorInstanceRead

orchestrator_router = APIRouter(prefix="")
orchestrator_api = FakeOrchestrator()


def _get_challenge_crud():
    return challenge_registry.get("orchestrator").crud


async def _resolve(session: SessionDep, challenge_id: UUID, user: User) -> tuple:
    if not user.team_id:
        raise NoTeamError()
    challenge = await _get_challenge_crud().get(
        session=session, filters=[_get_challenge_crud().model.id == challenge_id]
    )
    return challenge, user.team_id


@orchestrator_router.get("/status")
async def orchestrator_status(
    session: SessionDep,
    challenge_id: UUID,
    user: User = Security(auth),
) -> Response[PublicOrchestratorInstanceRead | None]:
    challenge, team_id = await _resolve(session, challenge_id, user)
    result = orchestrator_api.status(
        team_id=team_id, orchestrator_id=challenge.orchestrator_id
    )
    if not result:
        return Response(data=None)
    return Response(data=PublicOrchestratorInstanceRead(**result))


@orchestrator_router.post("/start")
async def orchestrator_start(
    session: SessionDep,
    challenge_id: UUID,
    user: User = Security(auth),
) -> Response[PublicOrchestratorInstanceRead]:
    challenge, team_id = await _resolve(session, challenge_id, user)
    return Response(
        data=PublicOrchestratorInstanceRead(
            **orchestrator_api.start(
                team_id=team_id, orchestrator_id=challenge.orchestrator_id
            )
        )
    )


@orchestrator_router.post("/stop")
async def orchestrator_stop(
    session: SessionDep,
    challenge_id: UUID,
    user: User = Security(auth),
) -> Response[PublicOrchestratorInstanceRead | None]:
    challenge, team_id = await _resolve(session, challenge_id, user)
    result = orchestrator_api.stop(
        team_id=team_id, orchestrator_id=challenge.orchestrator_id
    )
    if not result:
        return Response(data=None)
    return Response(data=PublicOrchestratorInstanceRead(**result))


@orchestrator_router.post("/renew")
async def orchestrator_renew(
    session: SessionDep,
    challenge_id: UUID,
    user: User = Security(auth),
) -> Response[PublicOrchestratorInstanceRead | None]:
    challenge, team_id = await _resolve(session, challenge_id, user)
    result = orchestrator_api.renew(
        team_id=team_id, orchestrator_id=challenge.orchestrator_id
    )
    if not result:
        return Response(data=None)
    return Response(data=PublicOrchestratorInstanceRead(**result))
