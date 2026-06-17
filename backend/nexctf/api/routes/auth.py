"""Authentication action endpoints: register, login, logout, OAuth flow."""

from typing import Annotated, Any, cast
from urllib.parse import urlparse
from uuid import UUID

import pyotp
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.responses import Response as RawResponse
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from redis.asyncio import Redis
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.exceptions import (
    AccountDisabledError,
    InvalidCredentialsError,
    InvalidOtpError,
    InvalidResetTokenError,
    OAuthAccountAlreadyLinkedError,
    OAuthProviderConfigError,
    OAuthProviderResponseError,
    RegistrationDisabledError,
    TotpRequiredError,
)
from fastapi_toolsets.security import (
    oauth_build_authorization_redirect,
    oauth_decode_state,
    oauth_fetch_userinfo,
    oauth_generate_state_token,
    oauth_resolve_provider_urls,
)
from sqlalchemy.orm import selectinload

import nexctf.core.appconfig as appconfig
import nexctf.crud as crud
from nexctf.api.dep import ProviderDep, RedisDep, SessionDep
from nexctf.core.rate_limit import check_rate_limit
from nexctf.api.security import (
    PWD_RESET_KEY_PREFIX,
    _hash_token,
    cookie_auth,
    dummy_verify_password,
    hash_password,
    verify_password,
)
from nexctf.core.captcha import verify_captcha
from nexctf.core.config import settings
from nexctf.model import OAuthAccount, OAuthProvider, User, UserToken
from nexctf.util.ip import get_client_ip
from nexctf.module.events import emit
from nexctf.schema import (
    OAuthAccountCreate,
    PublicRegisterRequest,
    PublicUserRead,
    UserCreate,
)
from nexctf.schema.user import PasswordResetRequest, UserPasswordUpdate

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", status_code=201)
async def register(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    obj: PublicRegisterRequest,
):
    if not appconfig.get("ctf.allow_registration"):
        raise RegistrationDisabledError()
    await verify_captcha(redis, obj.cap_token)
    client_ip = get_client_ip(request) or "unknown"
    await check_rate_limit(
        redis, f"rl:register:{client_ip}", window_seconds=60, max_requests=5
    )
    existing = await crud.UserCrud.first(
        session=session, filters=[User.username == obj.username]
    )
    if existing:
        raise ConflictError(detail="Username already taken")
    result = await crud.UserCrud.create(
        session=session,
        obj=UserCreate(
            username=obj.username,
            email=obj.email,
            hashed_password=hash_password(obj.password),
        ),
        schema=PublicUserRead,
    )
    if result.data is not None:
        await emit(
            session,
            redis,
            event_type="user.register",
            actor_id=result.data.id,
            ip=client_ip,
            meta={"username": result.data.username},
        )
    return result


async def _record_login_failure(
    session: AsyncSession,
    redis: Redis,
    *,
    username: str,
    ip: str,
    actor_id: UUID | None,
    reason: str,
) -> None:
    """Persist a failed-login audit event, committing so it survives the raise.

    The login handler raises an HTTP error right after, which would otherwise
    roll the event back before the request-end commit runs.
    """
    await emit(
        session,
        redis,
        event_type="user.login_failed",
        actor_id=actor_id,
        ip=ip,
        meta={"username": username, "reason": reason},
    )
    await session.commit()


@auth_router.post("/token", status_code=204)
async def login(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    response: RawResponse,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    totp_code: Annotated[str | None, Form()] = None,
    cap_token: Annotated[str | None, Form()] = None,
):
    await verify_captcha(redis, cap_token)
    client_ip = get_client_ip(request) or "unknown"
    if appconfig.get("rate_limit.login.enabled"):
        await check_rate_limit(
            redis,
            f"rl:login:{client_ip}",
            window_seconds=int(appconfig.get("rate_limit.login.window_seconds")),
            max_requests=int(appconfig.get("rate_limit.login.max_requests")),
        )
    user = await crud.UserCrud.first(
        session=session, filters=[User.username == username]
    )
    # Always perform an Argon2 verification — against a dummy hash when the user
    # is missing or has no password — so login timing does not reveal which
    # usernames exist (user enumeration via response timing).
    if user and user.hashed_password:
        password_valid = verify_password(password, user.hashed_password)
    else:
        dummy_verify_password(password)
        password_valid = False
    if not user or not password_valid or not user.is_active:
        if not user:
            reason = "unknown_user"
        elif not password_valid:
            reason = "bad_password"
        else:
            reason = "disabled"
        await _record_login_failure(
            session,
            redis,
            username=username,
            ip=client_ip,
            actor_id=user.id if user else None,
            reason=reason,
        )
        raise InvalidCredentialsError()
    if user.totp_secret:
        if not totp_code:
            raise TotpRequiredError()
        if not pyotp.TOTP(user.totp_secret).verify(totp_code, valid_window=1):
            await _record_login_failure(
                session,
                redis,
                username=username,
                ip=client_ip,
                actor_id=user.id,
                reason="bad_totp",
            )
            raise InvalidOtpError()
    cookie_auth.set_cookie(response, f"{user.id}:{user.session_version}")
    await emit(
        session,
        redis,
        event_type="user.login",
        actor_id=user.id,
        ip=client_ip,
        meta={"username": user.username},
    )


@auth_router.post("/reset-password", status_code=204)
async def reset_password(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    body: PasswordResetRequest,
):
    """Consume a single-use password reset token and update the user's password."""
    client_ip = get_client_ip(request) or "unknown"
    await check_rate_limit(
        redis, f"rl:pwd_reset:{client_ip}", window_seconds=60, max_requests=5
    )
    redis_key = f"{PWD_RESET_KEY_PREFIX}{_hash_token(body.token)}"
    # GETDEL is atomic: the token is consumed on first read, preventing double-use
    # under concurrent requests with the same token.
    user_id_str = await cast(Any, redis.getdel(redis_key))
    if not user_id_str:
        raise InvalidResetTokenError()
    user = await crud.UserCrud.first(
        session=session, filters=[User.id == UUID(user_id_str)]
    )
    if not user:
        raise NotFoundError()
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserPasswordUpdate(
            id=user.id, hashed_password=hash_password(body.new_password)
        ),
    )
    await crud.UserTokenCrud.delete(session, filters=[UserToken.user_id == user.id])
    await session.execute(
        sql_update(User)
        .where(User.id == user.id)
        .values(session_version=User.session_version + 1)
    )
    await emit(
        session,
        redis,
        event_type="user.password_reset",
        actor_id=user.id,
        ip=get_client_ip(request),
        meta={"username": user.username},
    )


async def _optional_cookie_user(request: Request) -> User | None:
    credential = await cookie_auth.extract(request)
    if credential is None:
        return None
    try:
        return await cookie_auth.authenticate(credential)
    except Exception:
        return None


@auth_router.post("/logout", status_code=204)
async def logout(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    response: RawResponse,
    user: User | None = Depends(_optional_cookie_user),
):
    cookie_auth.delete_cookie(response)
    if user is not None:
        await emit(
            session,
            redis,
            event_type="user.logout",
            actor_id=user.id,
            ip=get_client_ip(request),
            meta={"username": user.username},
        )


async def _resolve_user_from_userinfo(
    db: SessionDep,
    provider: OAuthProvider,
    userinfo: dict,
    *,
    current_user: User | None = None,
) -> tuple[User, bool]:
    """Return (user, is_new_user) for the given OAuth userinfo payload.

    Looks up an existing OAuthAccount by (provider, subject).  If none is
    found, links to *current_user* when a session is already active, otherwise
    creates a brand-new account.  Email-based auto-linking is intentionally
    omitted: an unverified provider email could silently take over an existing
    local account.
    """
    subject = userinfo.get("sub") or userinfo.get("id")
    if not subject:
        raise OAuthProviderResponseError()

    oauth_account = await crud.OAuthAccountCrud.first(
        session=db,
        filters=[
            OAuthAccount.provider_id == provider.id,
            OAuthAccount.subject == subject,
        ],
        load_options=[selectinload(OAuthAccount.user)],
    )
    if oauth_account:
        if current_user is not None and oauth_account.user_id != current_user.id:
            # The provider identity belongs to a different account. Silently
            # overwriting the session would be an implicit account switch —
            # raise an explicit error so the user knows what happened.
            raise OAuthAccountAlreadyLinkedError()
        return oauth_account.user, False

    if current_user is not None:
        user = current_user
        is_new_user = False
    else:
        email = userinfo.get("email")
        # Only use the email if it is not already claimed by another local account.
        # Assigning a conflicting email would raise a unique constraint violation, and
        # auto-linking by email (even here) opens an account-takeover vector.
        if email:
            conflict = await crud.UserCrud.first(
                session=db, filters=[User.email == email]
            )
            if conflict:
                email = None
        user = await crud.UserCrud.create(
            session=db,
            obj=UserCreate(
                username=userinfo.get("preferred_username")
                or userinfo.get("login")
                or subject,
                email=email,
            ),
        )
        is_new_user = True

    await crud.OAuthAccountCrud.create(
        session=db,
        obj=OAuthAccountCreate(
            user_id=user.id,
            provider_id=provider.id,
            subject=subject,
        ),
    )
    return user, is_new_user


_ALLOWED_REDIRECT_ORIGINS = {
    urlparse(settings.FRONTEND_HOST).netloc,
    urlparse(settings.BACKEND_HOST).netloc,
}


@auth_router.get("/providers/{slug}/authorize")
async def oauth_authorize(
    db: SessionDep,
    slug: str,
    provider: OAuthProvider = ProviderDep,
    redirect_url: str | None = None,
) -> RedirectResponse:
    if not provider.is_active:
        raise NotFoundError()

    authorization_url, _, _ = await oauth_resolve_provider_urls(
        discovery_url=provider.discovery_url
    )
    destination = (
        redirect_url
        if redirect_url and urlparse(redirect_url).netloc in _ALLOWED_REDIRECT_ORIGINS
        else settings.FRONTEND_HOST
    )
    state_token = oauth_generate_state_token()
    redirect = oauth_build_authorization_redirect(
        authorization_url,
        client_id=provider.client_id,
        scopes=provider.scopes,
        redirect_uri=f"{settings.BACKEND_HOST}{settings.API_V1_STR}/auth/providers/{slug}/callback",
        destination=destination,
        state_token=state_token,
    )
    redirect.set_cookie(
        f"oauth_state_{slug}",
        state_token,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
    )
    return redirect


@auth_router.get("/providers/{slug}/callback")
async def oauth_callback(
    request: Request,
    db: SessionDep,
    redis: RedisDep,
    slug: str,
    code: str,
    provider: OAuthProvider = ProviderDep,
    state: str | None = None,
    current_user: User | None = Depends(_optional_cookie_user),
) -> RedirectResponse:
    if not provider.is_active:
        raise NotFoundError()

    # Consume CSRF state token immediately — single-use regardless of what follows.
    expected_state_token = request.cookies.get(f"oauth_state_{slug}")
    if not expected_state_token or not state:
        # No state cookie means the user never went through /authorize on this
        # browser — reject to prevent CSRF login confusion attacks.
        raise InvalidCredentialsError()
    destination = oauth_decode_state(
        state,
        expected_state_token=expected_state_token,
        fallback=settings.FRONTEND_HOST,
    )
    redirect = RedirectResponse(url=destination, status_code=302)
    redirect.delete_cookie(
        f"oauth_state_{slug}",
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
    )

    _, token_url, userinfo_url = await oauth_resolve_provider_urls(
        provider.discovery_url
    )
    if not userinfo_url:
        raise OAuthProviderConfigError()

    userinfo = await oauth_fetch_userinfo(
        token_url=token_url,
        userinfo_url=userinfo_url,
        code=code,
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        redirect_uri=f"{settings.BACKEND_HOST}{settings.API_V1_STR}/auth/providers/{slug}/callback",
    )

    user, is_new_user = await _resolve_user_from_userinfo(
        db, provider, userinfo, current_user=current_user
    )

    if not user.is_active:
        raise AccountDisabledError()

    client_ip = get_client_ip(request)
    if is_new_user:
        await emit(
            db,
            redis,
            event_type="user.register",
            actor_id=user.id,
            ip=client_ip,
            meta={"username": user.username, "provider": provider.slug},
        )
    await emit(
        db,
        redis,
        event_type="user.login",
        actor_id=user.id,
        ip=client_ip,
        meta={"username": user.username, "provider": provider.slug},
    )

    cookie_auth.set_cookie(redirect, f"{user.id}:{user.session_version}")
    return redirect
