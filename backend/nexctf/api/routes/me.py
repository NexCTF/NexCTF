"""Current-user self-management endpoints."""

from datetime import UTC, datetime
from uuid import UUID

import pyotp
from fastapi import APIRouter, Request
from fastapi.responses import Response as RawResponse
from fastapi_multiauth import hash_token
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from fastapi_toolsets.schemas import PaginatedResponse, PaginationType, Response
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.api.dep import (
    ConfigDep,
    CurrentUserDep,
    RedisDep,
    SessionDep,
    can_view_scoreboard,
)
from nexctf.api.security import (
    cookie_auth,
    create_api_token,
    hash_password,
    issue_session_cookie,
    verify_password,
)
from nexctf.core import appconfig
from nexctf.exceptions import (
    AlreadyInTeamError,
    CannotUnlinkLastOAuthError,
    InvalidCredentialsError,
    InvalidInviteCodeError,
    InvalidOtpError,
    NotInTeamError,
    TeamChangesDisabledError,
    TeamCreationDisabledError,
    TeamFullError,
    TotpAlreadyEnabledError,
    TotpNotEnabledError,
)
from nexctf.model import OAuthAccount, Team, User, UserSession, UserToken
from nexctf.model.user import gen_invite_code
from nexctf.module.events import emit
from nexctf.module.session import revoke_user_sessions
from nexctf.module.team import load_team_read
from nexctf.schema import (
    PublicApiTokenCreate,
    PublicApiTokenRead,
    PublicOAuthAccountRead,
    PublicUserSessionRead,
    UserTeamUpdate,
    UserTotpUpdate,
)
from nexctf.schema.team import MyTeamRead, TeamCreate, TeamJoinRequest
from nexctf.schema.user import (
    PasswordChangeRequest,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpSetupResponse,
    UserPasswordUpdate,
)
from nexctf.util.ip import get_client_ip

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


@me_router.get("/sessions")
async def list_sessions(
    request: Request,
    session: SessionDep,
    user: CurrentUserDep,
) -> Response[list[PublicUserSessionRead]]:
    """List the user's live sessions, newest activity first."""
    rows = await crud.UserSessionCrud.get_multi(
        session=session,
        filters=[
            UserSession.user_id == user.id,
            UserSession.expires_at > datetime.now(UTC),
        ],
        order_by=UserSession.last_seen_at.desc(),
    )
    sid = cookie_auth.session_id_of(request)
    this_hash = hash_token(sid) if sid else None
    return Response(
        data=[
            PublicUserSessionRead(
                id=row.id,
                ip=row.ip,
                user_agent=row.user_agent,
                last_seen_at=row.last_seen_at,
                current=row.sid_hash == this_hash,
            )
            for row in rows
        ]
    )


@me_router.delete("/sessions/{session_id}", status_code=204)
async def revoke_one_session(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    session_id: UUID,
    user: CurrentUserDep,
):
    """Sign out one device."""
    row = await crud.UserSessionCrud.first(
        session=session,
        filters=[UserSession.id == session_id, UserSession.user_id == user.id],
    )
    if not row:
        raise NotFoundError(detail="Session not found")
    await crud.UserSessionCrud.delete(
        session=session, filters=[UserSession.id == row.id]
    )
    await emit(
        session,
        redis,
        event_type="user.session_revoked",
        actor_id=user.id,
        ip=get_client_ip(request),
    )


@me_router.delete("/sessions", status_code=204)
async def revoke_all_sessions(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    response: RawResponse,
    user: CurrentUserDep,
):
    """Sign out every device, including the one making the request.

    Included so a user who suspects their cookie was stolen can end every
    session without having to guess which one is the attacker's.
    """
    await revoke_user_sessions(session, user)
    cookie_auth.delete_cookie(response)
    await emit(
        session,
        redis,
        event_type="user.sessions_revoked",
        actor_id=user.id,
        ip=get_client_ip(request),
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


@me_router.post("/password", status_code=204)
async def change_password(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    response: RawResponse,
    body: PasswordChangeRequest,
    user: CurrentUserDep,
):
    """Verify the current password, replace it, and log out other sessions."""
    if not user.hashed_password or not verify_password(
        body.current_password, user.hashed_password
    ):
        raise InvalidCredentialsError()
    session_version = user.session_version + 1
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserPasswordUpdate(
            id=user.id,
            hashed_password=hash_password(body.new_password),
            session_version=session_version,
        ),
    )
    # Reflect the bump on the instance so the re-issued cookie carries it.
    user.session_version = session_version
    await revoke_user_sessions(session, user)
    await issue_session_cookie(session, response, user, request)
    await emit(
        session,
        redis,
        event_type="user.password_changed",
        actor_id=user.id,
        ip=get_client_ip(request),
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


@me_router.get("/team")
async def get_my_team(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    user: CurrentUserDep,
) -> Response[MyTeamRead | None]:
    if user.team_id is None:
        return Response(data=None)
    team = await load_team_read(
        session,
        redis,
        user.team_id,
        overrides=overrides,
        include_rank=can_view_scoreboard(user, overrides),
        live=True,
    )
    if team is None:
        raise NotFoundError()
    return Response(data=team)


@me_router.post("/team", status_code=201)
async def create_team(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    body: TeamCreate,
    user: CurrentUserDep,
) -> Response[MyTeamRead]:
    if not appconfig.get_with_overrides("ctf.allow_team_changes", overrides):
        raise TeamChangesDisabledError()
    if not appconfig.get_with_overrides("ctf.allow_team_creation", overrides):
        raise TeamCreationDisabledError()
    if user.team_id is not None:
        raise AlreadyInTeamError()
    if await crud.TeamCrud.first(session=session, filters=[Team.name == body.name]):
        raise ConflictError(detail="Team name already taken")

    team = await crud.TeamCrud.create(session, body)
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

    data = await load_team_read(
        session,
        redis,
        team.id,
        overrides=overrides,
        include_rank=can_view_scoreboard(user, overrides),
        live=True,
    )
    if data is None:
        raise NotFoundError()
    return Response(data=data)


@me_router.post("/team/join")
async def join_team(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    body: TeamJoinRequest,
    user: CurrentUserDep,
) -> Response[MyTeamRead]:
    if not appconfig.get_with_overrides("ctf.allow_team_changes", overrides):
        raise TeamChangesDisabledError()
    if user.team_id is not None:
        raise AlreadyInTeamError()

    team = await crud.TeamCrud.first(
        session,
        [Team.invite_code == body.code],
        load_options=[selectinload(Team.users)],
    )
    if team is None:
        raise InvalidInviteCodeError()
    if len(team.users) >= int(appconfig.get_with_overrides("ctf.team_size", overrides)):
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

    data = await load_team_read(
        session,
        redis,
        team.id,
        overrides=overrides,
        include_rank=can_view_scoreboard(user, overrides),
        live=True,
    )
    if data is None:
        raise NotFoundError()
    return Response(data=data)


@me_router.post("/team/leave", status_code=204)
async def leave_team(
    session: SessionDep,
    redis: RedisDep,
    overrides: ConfigDep,
    user: CurrentUserDep,
):
    if not appconfig.get_with_overrides("ctf.allow_team_changes", overrides):
        raise TeamChangesDisabledError()
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
    overrides: ConfigDep,
    user: CurrentUserDep,
) -> Response[str]:
    if not appconfig.get_with_overrides("ctf.allow_team_changes", overrides):
        raise TeamChangesDisabledError()
    if user.team_id is None:
        raise NotInTeamError()
    team = await crud.TeamCrud.first(
        session, [Team.id == user.team_id], load_options=[]
    )
    if team is None:
        raise NotFoundError()
    team.invite_code = gen_invite_code()
    return Response(data=team.invite_code)
