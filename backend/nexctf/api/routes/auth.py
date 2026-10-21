"""Authentication action endpoints: register, login, logout, OAuth flow."""

import logging
import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated, NamedTuple
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.responses import Response as RawResponse
from fastapi_multiauth.oauth import (
    oauth_build_authorization_redirect,
    oauth_decode_state,
    oauth_exchange_code,
    oauth_fetch_userinfo,
    oauth_generate_nonce,
    oauth_generate_pkce_pair,
    oauth_generate_state_token,
    oauth_resolve_provider_urls,
    oauth_validate_id_token,
)
from fastapi_toolsets.exceptions import ConflictError, NotFoundError
from redis.asyncio import Redis
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexctf import crud
from nexctf.api.dep import (
    ConfigDep,
    ProviderDep,
    RedisDep,
    SessionDep,
    SessionOnlyDep,
)
from nexctf.api.security import (
    EMAIL_VERIFY_KEY_PREFIX,
    EMAIL_VERIFY_TTL,
    consume_password_reset_token,
    consume_single_use_token,
    cookie_auth,
    dummy_verify_password,
    hash_password,
    issue_password_reset_token,
    issue_session_cookie,
    issue_single_use_token,
    password_reset_link,
    reissue_session_cookie,
    verify_password,
    verify_totp_once,
)
from nexctf.core import appconfig
from nexctf.core.captcha import create_challenge, verify_captcha
from nexctf.core.config import settings
from nexctf.core.email import dispatch_email
from nexctf.core.email_render import (
    build_password_reset_email,
    build_verification_email,
)
from nexctf.core.eventbus import close_user_streams
from nexctf.core.logging import bind_user_context
from nexctf.core.rate_limit import (
    check_config_rate_limit,
    check_rate_limit,
    client_rate_key,
)
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
from nexctf.model import OAuthAccount, OAuthProvider, User
from nexctf.module.events import emit
from nexctf.module.session import (
    FAILED_LOGIN_EVENT,
    LOGIN_EVENT,
    replace_password,
    revoke_session,
    team_meta,
)
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
    ReauthRequest,
    ResendVerificationRequest,
    UserEmailVerifiedUpdate,
)
from nexctf.util.ip import get_client_ip

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _email_enabled(overrides: dict[str, str]) -> bool:
    """Read email.enabled from the given config snapshot."""
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
        redis, EMAIL_VERIFY_KEY_PREFIX, EMAIL_VERIFY_TTL, str(user_id)
    )
    link = f"{settings.FRONTEND_HOST}/verify-email?token={token}"
    background_tasks.add_task(
        _deliver_branded_email, redis, email, link, build_verification_email
    )


@auth_router.get("/captcha/challenge")
async def captcha_challenge(request: Request, redis: RedisDep) -> dict:
    """Issue an ALTCHA challenge for the login and register widgets."""
    await check_rate_limit(
        redis,
        client_rate_key("captcha", request),
        name="captcha",
        window_seconds=60,
        max_requests=30,
    )
    return create_challenge()


@auth_router.post("/register", status_code=201)
async def register(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    overrides: ConfigDep,
    obj: PublicRegisterRequest,
):
    if not appconfig.get_with_overrides("ctf.allow_registration", overrides):
        raise RegistrationDisabledError()
    await verify_captcha(redis, overrides, obj.captcha_token)
    client_ip = get_client_ip(request)
    await check_rate_limit(
        redis,
        client_rate_key("register", request),
        name="register",
        window_seconds=60,
        max_requests=5,
    )
    # When SMTP is enabled an email is mandatory: it is the verification channel
    # and the login gate keys off it. With SMTP off, email stays optional.
    email_enabled = _email_enabled(overrides)
    if email_enabled and not obj.email:
        raise EmailRequiredError()
    try:
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
    except IntegrityError:
        raise ConflictError(detail="Username or email already taken")
    if result.data is not None:
        bind_user_context(result.data.id, result.data.username)
        logger.info("registered %s", result.data.username)
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
    ip: str | None,
    actor_id: UUID | None,
    reason: str,
) -> None:
    """Persist a failed-login audit event, committing so it survives the raise.

    The login handler raises an HTTP error right after, which would otherwise
    roll the event back before the request-end commit runs.
    """
    logger.warning(
        "login failed for %s (%s)",
        username,
        reason,
        extra={"username": username, "reason": reason},
    )
    await emit(
        session,
        redis,
        event_type=FAILED_LOGIN_EVENT,
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
    overrides: ConfigDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    totp_code: Annotated[str | None, Form()] = None,
    captcha_token: Annotated[str | None, Form()] = None,
):
    await verify_captcha(redis, overrides, captcha_token)
    client_ip = get_client_ip(request)
    await check_config_rate_limit(
        redis, overrides, name="login", key=client_rate_key("login", request)
    )
    user = await crud.UserCrud.first(
        session=session, filters=[func.lower(User.username) == username.lower()]
    )
    # Always perform an Argon2 verification — against a dummy hash when the user
    # is missing or has no password — so login timing does not reveal which
    # usernames exist (user enumeration via response timing).
    if user and user.hashed_password:
        password_valid = verify_password(password, user.hashed_password)
    else:
        dummy_verify_password(password)
        password_valid = False
    if not user or not password_valid:
        await _record_login_failure(
            session,
            redis,
            username=username,
            ip=client_ip,
            actor_id=user.id if user else None,
            reason="bad_password" if user else "unknown_user",
        )
        raise InvalidCredentialsError()
    if not user.is_active:
        await _record_login_failure(
            session,
            redis,
            username=username,
            ip=client_ip,
            actor_id=user.id,
            reason="disabled",
        )
        raise AccountDisabledError()
    if user.totp_secret:
        if not totp_code:
            raise TotpRequiredError()
        if not await verify_totp_once(redis, user.id, user.totp_secret, totp_code):
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
    if user.email and not user.email_verified and _email_enabled(overrides):
        await _record_login_failure(
            session,
            redis,
            username=username,
            ip=client_ip,
            actor_id=user.id,
            reason="email_not_verified",
        )
        raise EmailNotVerifiedError()
    await issue_session_cookie(session, response, user, request)
    bind_user_context(user.id, user.username)
    logger.info("login for %s", user.username)
    await emit(
        session,
        redis,
        event_type=LOGIN_EVENT,
        actor_id=user.id,
        ip=client_ip,
        meta={"username": user.username, **team_meta(user)},
    )


async def _reauth_failure_reason(
    redis: Redis, user: User, body: ReauthRequest
) -> str | None:
    """Why *body* does not re-prove *user*'s identity, or None when it does."""
    if not (user.hashed_password or user.totp_secret):
        return "no_factor"
    if user.hashed_password and not verify_password(
        body.password or "", user.hashed_password
    ):
        return "bad_password"
    if user.totp_secret:
        if not body.totp_code:
            raise TotpRequiredError()
        if not await verify_totp_once(redis, user.id, user.totp_secret, body.totp_code):
            return "bad_totp"
    return None


@auth_router.post("/reauth", status_code=204)
async def reauth(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    response: RawResponse,
    overrides: ConfigDep,
    body: ReauthRequest,
    user: SessionOnlyDep,
):
    """Re-prove the signed-in user's identity and re-sign this session in place.

    Takes the password, plus a TOTP code when 2FA is on; an account without a
    password re-proves with its TOTP code alone, or by signing in through OAuth.
    """
    await check_config_rate_limit(
        redis, overrides, name="login", key=client_rate_key("login", request)
    )
    client_ip = get_client_ip(request)
    reason = await _reauth_failure_reason(redis, user, body)
    if reason is not None:
        await _record_login_failure(
            session,
            redis,
            username=user.username,
            ip=client_ip,
            actor_id=user.id,
            reason=f"reauth_{reason}",
        )
        raise InvalidOtpError() if reason == "bad_totp" else InvalidCredentialsError()
    await reissue_session_cookie(session, response, user, request)
    logger.info("reauth for %s", user.username)
    await emit(
        session,
        redis,
        event_type="user.reauth",
        actor_id=user.id,
        ip=client_ip,
        meta={"username": user.username},
    )


@auth_router.post("/reset-password", status_code=204)
async def reset_password(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    background_tasks: BackgroundTasks,
    body: PasswordResetRequest,
):
    """Consume a single-use password reset token and update the user's password."""
    await check_rate_limit(
        redis,
        client_rate_key("pwd_reset", request),
        name="pwd_reset",
        window_seconds=60,
        max_requests=5,
    )
    consumed = await consume_password_reset_token(redis, body.token)
    if consumed is None:
        raise InvalidResetTokenError()
    user_id, session_version = consumed
    user = await crud.UserCrud.first(session=session, filters=[User.id == user_id])
    if not user:
        raise NotFoundError()
    if session_version != user.session_version:
        raise InvalidResetTokenError()
    bind_user_context(user.id, user.username)
    await replace_password(session, user, hash_password(body.new_password))
    background_tasks.add_task(close_user_streams, redis, user.id)
    logger.info("password reset completed for %s", user.username)
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
    client_ip = get_client_ip(request)
    await check_rate_limit(
        redis,
        client_rate_key("verify_email", request),
        name="verify_email",
        window_seconds=60,
        max_requests=10,
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
    bind_user_context(user.id, user.username)
    logger.info("email verified for %s", user.username)
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
    overrides: dict[str, str],
    rate_limit_action: str,
) -> tuple[User | None, str | None]:
    """Rate-limit, gate on email.enabled, and look up the user case-insensitively."""
    client_ip = get_client_ip(request)
    await check_rate_limit(
        redis,
        client_rate_key(rate_limit_action, request),
        name=rate_limit_action,
        window_seconds=60,
        max_requests=3,
    )
    if not _email_enabled(overrides):
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
    overrides: ConfigDep,
    body: ResendVerificationRequest,
):
    """Re-send the verification email. Always 204 to avoid account enumeration."""
    user, client_ip = await _email_action_recipient(
        request,
        session,
        redis,
        body.email,
        overrides=overrides,
        rate_limit_action="resend_verify",
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
    overrides: ConfigDep,
    body: ForgotPasswordRequest,
):
    """Email a single-use password reset link. Always 204 to avoid enumeration."""
    user, client_ip = await _email_action_recipient(
        request,
        session,
        redis,
        body.email,
        overrides=overrides,
        rate_limit_action="forgot_password",
    )
    if not user or not user.email:
        return
    token = await issue_password_reset_token(redis, user)
    link = password_reset_link(token)
    background_tasks.add_task(
        _deliver_branded_email, redis, user.email, link, build_password_reset_email
    )
    bind_user_context(user.id, user.username)
    logger.info("password reset requested for %s", user.username)
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
        return await cookie_auth.authenticate(credential, request=request)
    except Exception:  # noqa: BLE001
        return None


OptionalCookieUserDep = Annotated[User | None, Depends(_optional_cookie_user)]


@auth_router.post("/logout", status_code=204)
async def logout(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    response: RawResponse,
    user: OptionalCookieUserDep,
):
    sid = cookie_auth.delete_cookie(response, request)
    if sid is not None:
        await revoke_session(session, sid)
    if user is not None:
        await emit(
            session,
            redis,
            event_type="user.logout",
            actor_id=user.id,
            ip=get_client_ip(request),
            meta={"username": user.username},
        )


async def _unique_username(db: SessionDep, desired: str) -> str:
    """Return *desired*, suffixed if another local account already holds it."""
    candidate = desired
    while await crud.UserCrud.exists(
        session=db, filters=[func.lower(User.username) == candidate.lower()]
    ):
        candidate = f"{desired}-{secrets.token_hex(3)}"
    return candidate


async def _resolve_user_from_userinfo(
    db: SessionDep,
    provider: OAuthProvider,
    subject: str,
    userinfo: dict,
    *,
    current_user: User | None = None,
    allow_registration: bool = True,
) -> tuple[User, bool]:
    """Return (user, is_new_user) for the verified *subject* and its userinfo.

    Looks up an existing OAuthAccount by (provider, subject).  If none is
    found, links to *current_user* when a session is already active, otherwise
    creates a brand-new account when *allow_registration* is set.  Email-based auto-linking is intentionally
    omitted: an unverified provider email could silently take over an existing
    local account.
    """
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
        if not allow_registration:
            raise RegistrationDisabledError()
        email = (
            userinfo.get("email") if userinfo.get("email_verified") is True else None
        )
        # Only use the email if it is not already claimed by another local account.
        # Assigning a conflicting email would raise a unique constraint violation, and
        # auto-linking by email (even here) opens an account-takeover vector.
        if email:
            conflict = await crud.UserCrud.first(
                session=db, filters=[func.lower(User.email) == email.lower()]
            )
            if conflict:
                email = None
        username = await _unique_username(
            db,
            userinfo.get("preferred_username") or userinfo.get("login") or subject,
        )
        user = await crud.UserCrud.create(
            session=db,
            obj=UserCreate(
                username=username,
                email=email,
                # The provider asserted ownership of this address (email_verified).
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


_ALLOWED_REDIRECT_HOSTS = tuple(
    urlparse(host).hostname or ""
    for host in (settings.FRONTEND_HOST, settings.BACKEND_HOST)
)

_ID_TOKEN_LEEWAY = 60


class _ProviderEndpoints(NamedTuple):
    """The OIDC endpoints a provider sign-in needs."""

    authorization: str
    token: str
    userinfo: str
    jwks: str
    issuer: str


async def _provider_endpoints(provider: OAuthProvider) -> _ProviderEndpoints:
    """Discover *provider*'s endpoints, refusing a provider that lacks one."""
    found = await oauth_resolve_provider_urls(provider.discovery_url)
    if not (found.userinfo_endpoint and found.jwks_uri and found.issuer):
        raise OAuthProviderConfigError()
    return _ProviderEndpoints(
        authorization=found.authorization_endpoint,
        token=found.token_endpoint,
        userinfo=found.userinfo_endpoint,
        jwks=found.jwks_uri,
        issuer=found.issuer,
    )


def _callback_url(slug: str) -> str:
    """The redirect URI the provider sends the browser back to."""
    return (
        f"{settings.BACKEND_HOST}{settings.API_V1_STR}/auth/providers/{slug}/callback"
    )


def _flow_cookie(slug: str) -> str:
    """Name of the cookie carrying the state token, nonce and PKCE verifier."""
    return f"oauth_state_{slug}"


def _read_flow_cookie(request: Request, slug: str) -> tuple[str, str, str]:
    """The ``(state_token, nonce, code_verifier)`` stored by ``/authorize``."""
    parts = request.cookies.get(_flow_cookie(slug), "").split(".")
    # No flow cookie: this browser never went through /authorize.
    if len(parts) != 3 or not all(parts):
        raise InvalidCredentialsError()
    state_token, nonce, code_verifier = parts
    return state_token, nonce, code_verifier


async def _id_token_subject(
    provider: OAuthProvider, endpoints: _ProviderEndpoints, token: dict, nonce: str
) -> str:
    """The ``sub`` of the ID token in *token*, once validated against *nonce*."""
    id_token = token.get("id_token")
    if not isinstance(id_token, str):
        raise OAuthProviderResponseError()
    claims = await oauth_validate_id_token(
        id_token,
        issuer=endpoints.issuer,
        jwks_uri=endpoints.jwks,
        client_id=provider.client_id,
        nonce=nonce,
        leeway=_ID_TOKEN_LEEWAY,
    )
    return claims["sub"]


@auth_router.get("/providers/{slug}/authorize")
async def oauth_authorize(
    db: SessionDep,
    slug: str,
    provider: OAuthProvider = ProviderDep,
    redirect_url: str | None = None,
) -> RedirectResponse:
    if not provider.is_active:
        raise NotFoundError()

    endpoints = await _provider_endpoints(provider)
    destination = (
        redirect_url
        if redirect_url and urlparse(redirect_url).hostname in _ALLOWED_REDIRECT_HOSTS
        else settings.FRONTEND_HOST
    )
    state_token = oauth_generate_state_token()
    nonce = oauth_generate_nonce()
    code_verifier, code_challenge = oauth_generate_pkce_pair()
    redirect = oauth_build_authorization_redirect(
        endpoints.authorization,
        client_id=provider.client_id,
        scopes=provider.scopes,
        redirect_uri=_callback_url(slug),
        destination=destination,
        state_token=state_token,
        code_challenge=code_challenge,
        nonce=nonce,
    )
    redirect.set_cookie(
        _flow_cookie(slug),
        f"{state_token}.{nonce}.{code_verifier}",
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
    current_user: OptionalCookieUserDep,
    overrides: ConfigDep,
    provider: OAuthProvider = ProviderDep,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    if not provider.is_active:
        raise NotFoundError()

    # Consume CSRF state token immediately — single-use regardless of what follows.
    expected_state_token, nonce, code_verifier = _read_flow_cookie(request, slug)
    destination = oauth_decode_state(
        state,
        expected_state_token=expected_state_token,
        fallback="",
        allowed_hosts=_ALLOWED_REDIRECT_HOSTS,
    )
    if not destination:
        raise InvalidCredentialsError()

    redirect = RedirectResponse(url=destination, status_code=302)
    redirect.delete_cookie(
        _flow_cookie(slug),
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
    )

    # RFC 6749 §4.1.2.1: a denial arrives as ?error= with no code.
    if not code:
        return redirect

    endpoints = await _provider_endpoints(provider)
    token = await oauth_exchange_code(
        token_url=endpoints.token,
        code=code,
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        redirect_uri=_callback_url(slug),
        code_verifier=code_verifier,
    )
    subject = await _id_token_subject(provider, endpoints, token, nonce)
    userinfo = await oauth_fetch_userinfo(
        userinfo_url=endpoints.userinfo,
        access_token=token["access_token"],
    )
    # OIDC Core §5.3.2: the userinfo sub must equal the ID token's.
    if userinfo.get("sub") != subject:
        raise OAuthProviderResponseError()

    try:
        user, is_new_user = await _resolve_user_from_userinfo(
            db,
            provider,
            subject,
            userinfo,
            current_user=current_user,
            allow_registration=bool(
                appconfig.get_with_overrides("ctf.allow_registration", overrides)
            ),
        )
    except IntegrityError:
        raise ConflictError(detail="Another sign-in created this account; try again")

    if not user.is_active:
        raise AccountDisabledError()

    client_ip = get_client_ip(request)
    bind_user_context(user.id, user.username)
    logger.info(
        "oauth login for %s via %s",
        user.username,
        provider.slug,
        extra={"provider": provider.slug, "new_user": is_new_user},
    )
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
        event_type=LOGIN_EVENT,
        actor_id=user.id,
        ip=client_ip,
        meta={
            "username": user.username,
            "provider": provider.slug,
            **team_meta(user),
        },
    )

    if current_user is not None:
        await reissue_session_cookie(db, redirect, user, request)
    else:
        await issue_session_cookie(db, redirect, user, request)
    return redirect
