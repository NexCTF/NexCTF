"""Current-user self-management endpoints."""

import asyncio
import secrets
import string
from uuid import UUID

import pyotp
from fastapi import APIRouter, Request
from fastapi_toolsets.schemas import PaginatedResponse, PaginationType, Response
from sqlalchemy.orm import selectinload

import nexctf.core.appconfig as appconfig
import nexctf.crud as crud
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from nexctf.exceptions import (
    CannotUnlinkLastOAuthError,
    AlreadyInTeamError,
    InvalidInviteCodeError,
    InvalidOtpError,
    NotInTeamError,
    TeamCreationDisabledError,
    TeamFullError,
    TotpAlreadyEnabledError,
    TotpNotEnabledError,
)
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.api.security import create_api_token
from nexctf.util.ip import get_client_ip
from nexctf.module.events import emit
from nexctf.module.stats import get_team_challenge_stats
from nexctf.model import OAuthAccount, Team, User, UserToken
from nexctf.schema import (
    PublicApiTokenCreate,
    PublicApiTokenRead,
    PublicOAuthAccountRead,
    UserTeamUpdate,
    UserTotpUpdate,
)
from nexctf.schema.team import (
    TeamCreate,
    PublicTeamMember,
    PublicTeamRead,
    TeamCreateRequest,
    TeamJoinRequest,
)
from nexctf.schema.stats import TeamChallengeStats
from nexctf.schema.user import TotpDisableRequest, TotpEnableRequest, TotpSetupResponse

me_router = APIRouter(prefix="/me", tags=["me"])


@me_router.get("/tokens")
async def list_tokens(
    session: SessionDep,
    user: CurrentUserDep,
) -> PaginatedResponse[PublicApiTokenRead]:
    return await crud.UserTokenCrud.paginate(
        session=session,
        pagination_type=PaginationType.OFFSET,
        filters=[UserToken.user_id == user.id],
        items_per_page=100,
        page=1,
        schema=PublicApiTokenRead,
    )


@me_router.post("/tokens", status_code=201)
async def create_token(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    obj: PublicApiTokenCreate,
    user: CurrentUserDep,
) -> Response[PublicApiTokenRead]:
    raw, token_row = await create_api_token(
        user.id, name=obj.name, expires_at=obj.expires_at
    )
    await emit(
        session,
        redis,
        event_type="user.token_created",
        actor_id=user.id,
        ip=get_client_ip(request),
        meta={"token_name": obj.name},
    )
    return Response(
        data=PublicApiTokenRead(
            id=token_row.id,
            name=token_row.name,
            expires_at=token_row.expires_at,
            created_at=token_row.created_at,
            token=raw,
        )
    )


@me_router.delete("/tokens/{token_id}", status_code=204)
async def revoke_token(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    token_id: UUID,
    user: CurrentUserDep,
):
    token = await crud.UserTokenCrud.first(
        session=session,
        filters=[UserToken.id == token_id, UserToken.user_id == user.id],
    )
    if not token:
        raise NotFoundError(detail="Token not found")
    await crud.UserTokenCrud.delete(
        session=session,
        filters=[UserToken.id == token_id, UserToken.user_id == user.id],
    )
    await emit(
        session,
        redis,
        event_type="user.token_revoked",
        actor_id=user.id,
        ip=get_client_ip(request),
        meta={"token_name": token.name},
    )


@me_router.get("/oauth")
async def list_oauth_accounts(
    session: SessionDep,
    user: CurrentUserDep,
) -> Response[list[PublicOAuthAccountRead]]:
    """Return all OAuth providers linked to the current user's account."""
    accounts = await crud.OAuthAccountCrud.get_multi(
        session=session,
        filters=[OAuthAccount.user_id == user.id],
        load_options=[selectinload(OAuthAccount.provider)],
    )
    return Response(
        data=[
            PublicOAuthAccountRead(
                id=a.id,
                provider_slug=a.provider.slug,
                provider_name=a.provider.name,
                provider_icon_url=a.provider.icon_url,
            )
            for a in accounts
        ]
    )


@me_router.delete("/oauth/{account_id}", status_code=204)
async def unlink_oauth_account(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    account_id: UUID,
    user: CurrentUserDep,
):
    """Unlink an OAuth provider from the current user's account.

    Rejected when the user has no password and this is their only linked provider,
    which would lock them out.
    """
    account = await crud.OAuthAccountCrud.first(
        session=session,
        filters=[OAuthAccount.id == account_id, OAuthAccount.user_id == user.id],
        load_options=[selectinload(OAuthAccount.provider)],
    )
    if not account:
        raise NotFoundError(detail="OAuth account not found")

    if not user.hashed_password:
        total = await crud.OAuthAccountCrud.count(
            session=session, filters=[OAuthAccount.user_id == user.id]
        )
        if total <= 1:
            raise CannotUnlinkLastOAuthError()

    provider_slug = account.provider.slug
    await crud.OAuthAccountCrud.delete(
        session=session,
        filters=[OAuthAccount.id == account_id, OAuthAccount.user_id == user.id],
    )
    await emit(
        session,
        redis,
        event_type="user.oauth_unlinked",
        actor_id=user.id,
        ip=get_client_ip(request),
        meta={"provider": provider_slug},
    )


_TOTP_SETUP_PREFIX = "totp_setup:"
_TOTP_SETUP_TTL = 600  # 10 minutes


@me_router.post("/totp/setup")
async def totp_setup(
    redis: RedisDep,
    user: CurrentUserDep,
) -> Response[TotpSetupResponse]:
    """Generate a new TOTP secret and store it server-side (does not activate it yet)."""
    if user.totp_secret:
        raise TotpAlreadyEnabledError()
    secret = pyotp.random_base32()
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.username, issuer_name="NexCTF"
    )
    await redis.setex(_TOTP_SETUP_PREFIX + str(user.id), _TOTP_SETUP_TTL, secret)
    return Response(data=TotpSetupResponse(provisioning_uri=provisioning_uri))


@me_router.post("/totp/enable", status_code=204)
async def totp_enable(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    body: TotpEnableRequest,
    user: CurrentUserDep,
):
    """Read the provisional secret from Redis, verify the OTP code, and enable TOTP."""
    if user.totp_secret:
        raise TotpAlreadyEnabledError()
    secret = await redis.get(_TOTP_SETUP_PREFIX + str(user.id))
    if not secret:
        raise InvalidOtpError()
    secret_str = secret if isinstance(secret, str) else secret.decode()
    if not pyotp.TOTP(secret_str).verify(body.code, valid_window=1):
        raise InvalidOtpError()
    await redis.delete(_TOTP_SETUP_PREFIX + str(user.id))
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserTotpUpdate(id=user.id, totp_secret=secret_str),
    )
    await emit(
        session,
        redis,
        event_type="user.totp_enabled",
        actor_id=user.id,
        ip=get_client_ip(request),
    )


@me_router.post("/totp/disable", status_code=204)
async def totp_disable(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    body: TotpDisableRequest,
    user: CurrentUserDep,
):
    """Verify OTP code and disable TOTP."""
    if not user.totp_secret:
        raise TotpNotEnabledError()
    if not pyotp.TOTP(user.totp_secret).verify(body.code, valid_window=1):
        raise InvalidOtpError()
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserTotpUpdate(id=user.id, totp_secret=None),
    )
    await emit(
        session,
        redis,
        event_type="user.totp_disabled",
        actor_id=user.id,
        ip=get_client_ip(request),
    )


def _gen_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _build_team_read(
    team: Team,
    members: list[PublicTeamMember],
    stats: list[TeamChallengeStats],
) -> PublicTeamRead:
    return PublicTeamRead(
        id=team.id,
        name=team.name,
        country=team.country,
        bracket=team.bracket,
        members=members,
        challenge_stats=stats,
        invite_code=team.invite_code,
    )


@me_router.get("/team")
async def get_my_team(
    session: SessionDep,
    redis: RedisDep,
    user: CurrentUserDep,
) -> Response[PublicTeamRead | None]:
    if user.team_id is None:
        return Response(data=None)
    team, stats = await asyncio.gather(
        crud.TeamCrud.first(
            session, [Team.id == user.team_id], load_options=[selectinload(Team.users)]
        ),
        get_team_challenge_stats(session, redis, user.team_id),
    )
    if team is None:
        raise NotFoundError()
    members = [PublicTeamMember(id=u.id, username=u.username) for u in team.users]
    return Response(data=_build_team_read(team, members, stats))


@me_router.post("/team", status_code=201)
async def create_team(
    session: SessionDep,
    redis: RedisDep,
    body: TeamCreateRequest,
    user: CurrentUserDep,
) -> Response[PublicTeamRead]:
    if not appconfig.get("ctf.allow_team_creation"):
        raise TeamCreationDisabledError()
    if user.team_id is not None:
        raise AlreadyInTeamError()
    if await crud.TeamCrud.first(session=session, filters=[Team.name == body.name]):
        raise ConflictError(detail="Team name already taken")

    team = await crud.TeamCrud.create(
        session, TeamCreate(name=body.name, invite_code=_gen_invite_code())
    )
    await crud.UserCrud.update(
        session, UserTeamUpdate(team_id=team.id), [User.id == user.id]
    )
    await emit(
        session,
        redis,
        event_type="team.created",
        actor_id=user.id,
        meta={"team_name": team.name},
    )

    return Response(
        data=_build_team_read(
            team,
            [PublicTeamMember(id=user.id, username=user.username)],
            [],
        )
    )


@me_router.post("/team/join")
async def join_team(
    session: SessionDep,
    redis: RedisDep,
    body: TeamJoinRequest,
    user: CurrentUserDep,
) -> Response[PublicTeamRead]:
    if user.team_id is not None:
        raise AlreadyInTeamError()

    team = await crud.TeamCrud.first(
        session,
        [Team.invite_code == body.code],
        load_options=[selectinload(Team.users)],
    )
    if team is None:
        raise InvalidInviteCodeError()
    if len(team.users) >= int(appconfig.get("ctf.team_size")):
        raise TeamFullError()

    await crud.UserCrud.update(
        session, UserTeamUpdate(team_id=team.id), [User.id == user.id]
    )
    await emit(
        session,
        redis,
        event_type="team.joined",
        actor_id=user.id,
        meta={"team_name": team.name},
    )

    members = [
        *[PublicTeamMember(id=u.id, username=u.username) for u in team.users],
        PublicTeamMember(id=user.id, username=user.username),
    ]
    return Response(data=_build_team_read(team, members, []))


@me_router.post("/team/leave", status_code=204)
async def leave_team(
    session: SessionDep,
    redis: RedisDep,
    user: CurrentUserDep,
):
    if user.team_id is None:
        raise NotInTeamError()
    team = await crud.TeamCrud.first(
        session, [Team.id == user.team_id], load_options=[]
    )
    team_name = team.name if team else ""
    await crud.UserCrud.update(
        session, UserTeamUpdate(team_id=None), [User.id == user.id]
    )
    await emit(
        session,
        redis,
        event_type="team.left",
        actor_id=user.id,
        meta={"team_name": team_name},
    )


@me_router.post("/team/invite-code")
async def rotate_invite_code(
    session: SessionDep,
    user: CurrentUserDep,
) -> Response[str]:
    if not appconfig.get("ctf.allow_team_creation"):
        raise TeamCreationDisabledError()
    if user.team_id is None:
        raise NotInTeamError()
    team = await crud.TeamCrud.first(
        session, [Team.id == user.team_id], load_options=[]
    )
    if team is None:
        raise NotFoundError()
    team.invite_code = _gen_invite_code()
    return Response(data=team.invite_code)
