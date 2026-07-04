"""Authentication action endpoints: register, login, logout, OAuth flow."""

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

import pyotp
from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.responses import Response as RawResponse
from fastapi_multiauth.oauth import (
    oauth_build_authorization_redirect,
    oauth_decode_state,
    oauth_exchange_code,
    oauth_fetch_userinfo,
    oauth_generate_state_token,
    oauth_resolve_provider_urls,
)
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from redis.asyncio import Redis
from sqlalchemy import func
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import nexctf.core.appconfig as appconfig
import nexctf.crud as crud
from nexctf.api.dep import ProviderDep, RedisDep, SessionDep
from nexctf.api.security import (
    EMAIL_VERIFY_KEY_PREFIX,
    EMAIL_VERIFY_TTL,
    PWD_RESET_KEY_PREFIX,
    PWD_RESET_TTL,
    consume_single_use_token,
    cookie_auth,
    dummy_verify_password,
    hash_password,
    issue_single_use_token,
    verify_password,
)
from nexctf.core.captcha import verify_captcha
from nexctf.core.config import settings
from nexctf.core.email import dispatch_email
from nexctf.core.email_render import (
    build_password_reset_email,
    build_verification_email,
)
from nexctf.core.rate_limit import check_rate_limit
from nexctf.exceptions import (
    AccountDisabledError,
    EmailNotVerifiedError,
    EmailRequiredError,
    InvalidCredentialsError,
    InvalidOtpError,
    InvalidResetTokenError,
    InvalidVerificationTokenError,
    OAuthAccountAlreadyLinkedError,
    OAuthProviderConfigError,
    OAuthProviderResponseError,
    RegistrationDisabledError,
    TotpRequiredError,
)
from nexctf.model import OAuthAccount, OAuthProvider, User, UserToken
from nexctf.module.events import emit
from nexctf.schema import (
    OAuthAccountCreate,
    PublicRegisterRequest,
    PublicUserRead,
    UserCreate,
)
from nexctf.schema.user import (
    EmailVerifyRequest,
    ForgotPasswordRequest,
    PasswordResetRequest,
    ResendVerificationRequest,
    UserEmailVerifiedUpdate,
    UserPasswordUpdate,
)
from nexctf.util.ip import get_client_ip

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


async def _email_enabled(redis: Redis) -> bool:
    """Read email.enabled from a fresh Redis snapshot so all workers agree."""
    overrides = await appconfig.fetch_overrides(redis)
    return bool(appconfig.get_with_overrides("email.enabled", overrides))


async def _deliver_branded_email(
    redis: Redis,
    to: str,
    link: str,
    builder: Callable[[dict[str, str], str], Awaitable[tuple[str, str, str]]],
) -> None:
    """Render a branded email and send it. Run as a background task."""
    try:
        overrides = await appconfig.fetch_overrides(redis)
        subject, text, html = await builder(overrides, link)
    except Exception:
        logger.exception("failed to render branded email to %s", to)
        return
    await dispatch_email(redis, to, subject, text=text, html=html, overrides=overrides)


async def _send_verification_email(
    redis: Redis,
    background_tasks: BackgroundTasks,
    *,
    user_id: UUID,
    email: str,
) -> None:
    """Mint a single-use verification token and queue the branded email.

    The token is stored before returning so it is usable the moment the email
    arrives; branding/rendering and the send are deferred to a background task.
    """
    token = await issue_single_use_token(
        redis, EMAIL_VERIFY_KEY_PREFIX, EMAIL_VERIFY_TTL, user_id
    )
    link = f"{settings.FRONTEND_HOST}/verify-email?token={token}"
    background_tasks.add_task(
        _deliver_branded_email, redis, email, link, build_verification_email
    )


@auth_router.post("/register", status_code=201)
async def register(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
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
    # When SMTP is enabled an email is mandatory: it is the verification channel
    # and the login gate keys off it. With SMTP off, email stays optional.
    email_enabled = await _email_enabled(redis)
    if email_enabled and not obj.email:
        raise EmailRequiredError()
    result = await crud.UserCrud.create(
        session=session,
        obj=UserCreate(
            username=obj.username,
            email=obj.email,
            hashed_password=hash_password(obj.password),
            email_verified=not email_enabled,
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
        if email_enabled and obj.email:
            await _send_verification_email(
                redis, background_tasks, user_id=result.data.id, email=obj.email
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
    # Gate login on email verification, but only while SMTP is enabled — otherwise
    # users could never receive the verification email and would be locked out.
    if user.email and not user.email_verified and await _email_enabled(redis):
        await _record_login_failure(
            session,
            redis,
            username=username,
            ip=client_ip,
            actor_id=user.id,
            reason="email_not_verified",
        )
        raise EmailNotVerifiedError()
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
    user_id_str = await consume_single_use_token(
        redis, PWD_RESET_KEY_PREFIX, body.token
    )
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


@auth_router.post("/verify-email", status_code=204)
async def verify_email(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    body: EmailVerifyRequest,
):
    """Consume a single-use email verification token and mark the email verified."""
    client_ip = get_client_ip(request) or "unknown"
    await check_rate_limit(
        redis, f"rl:verify_email:{client_ip}", window_seconds=60, max_requests=10
    )
    user_id_str = await consume_single_use_token(
        redis, EMAIL_VERIFY_KEY_PREFIX, body.token
    )
    if not user_id_str:
        raise InvalidVerificationTokenError()
    user = await crud.UserCrud.first(
        session=session, filters=[User.id == UUID(user_id_str)]
    )
    if not user:
        raise InvalidVerificationTokenError()
    await crud.UserCrud.update(
        session=session,
        filters=[User.id == user.id],
        obj=UserEmailVerifiedUpdate(id=user.id, email_verified=True),
    )
    await emit(
        session,
        redis,
        event_type="user.email_verified",
        actor_id=user.id,
        ip=client_ip,
        meta={"username": user.username},
    )


async def _email_action_recipient(
    request: Request,
    session: SessionDep,
    redis: Redis,
    email: str,
    *,
    rate_limit_action: str,
) -> tuple[User | None, str]:
    """Rate-limit, gate on email.enabled, and look up the user case-insensitively."""
    client_ip = get_client_ip(request) or "unknown"
    await check_rate_limit(
        redis,
        f"rl:{rate_limit_action}:{client_ip}",
        window_seconds=60,
        max_requests=3,
    )
    if not await _email_enabled(redis):
        return None, client_ip
    user = await crud.UserCrud.first(
        session=session, filters=[func.lower(User.email) == email.lower()]
    )
    return user, client_ip


@auth_router.post("/resend-verification", status_code=204)
async def resend_verification(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    body: ResendVerificationRequest,
):
    """Re-send the verification email. Always 204 to avoid account enumeration."""
    user, client_ip = await _email_action_recipient(
        request, session, redis, body.email, rate_limit_action="resend_verify"
    )
    if user and user.email and not user.email_verified:
        await _send_verification_email(
            redis, background_tasks, user_id=user.id, email=user.email
        )
        await emit(
            session,
            redis,
            event_type="user.verification_resent",
            actor_id=user.id,
            ip=client_ip,
            meta={"username": user.username},
        )


@auth_router.post("/forgot-password", status_code=204)
async def forgot_password(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    body: ForgotPasswordRequest,
):
    """Email a single-use password reset link. Always 204 to avoid enumeration."""
    user, client_ip = await _email_action_recipient(
        request, session, redis, body.email, rate_limit_action="forgot_password"
    )
    if not user or not user.email:
        return
    token = await issue_single_use_token(
        redis, PWD_RESET_KEY_PREFIX, PWD_RESET_TTL, user.id
    )
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    background_tasks.add_task(
        _deliver_branded_email, redis, user.email, link, build_password_reset_email
    )
    await emit(
        session,
        redis,
        event_type="user.password_reset_requested",
        actor_id=user.id,
        ip=client_ip,
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
                # The OAuth provider already verified ownership of this address.
                email_verified=True,
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

    endpoints = await oauth_resolve_provider_urls(provider.discovery_url)
    destination = (
        redirect_url
        if redirect_url and urlparse(redirect_url).netloc in _ALLOWED_REDIRECT_ORIGINS
        else settings.FRONTEND_HOST
    )
    state_token = oauth_generate_state_token()
    redirect = oauth_build_authorization_redirect(
        endpoints.authorization_endpoint,
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
        allowed_hosts=tuple(_ALLOWED_REDIRECT_ORIGINS),
    )
    redirect = RedirectResponse(url=destination, status_code=302)
    redirect.delete_cookie(
        f"oauth_state_{slug}",
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
    )

    endpoints = await oauth_resolve_provider_urls(provider.discovery_url)
    if not endpoints.userinfo_endpoint:
        raise OAuthProviderConfigError()

    token = await oauth_exchange_code(
        token_url=endpoints.token_endpoint,
        code=code,
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        redirect_uri=f"{settings.BACKEND_HOST}{settings.API_V1_STR}/auth/providers/{slug}/callback",
    )
    userinfo = await oauth_fetch_userinfo(
        userinfo_url=endpoints.userinfo_endpoint,
        access_token=token["access_token"],
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
