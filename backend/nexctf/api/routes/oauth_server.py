import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from typing import Annotated
from urllib.parse import quote, urlencode
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_toolsets.schemas import Response
from sqlalchemy.ext.asyncio import AsyncSession

import nexctf.crud as crud
from nexctf.api.dep import CurrentUserDep, RedisDep, SessionDep
from nexctf.core.config import settings
from nexctf.model import User
from nexctf.model.oauth_server import OAuthServerClient
from nexctf.schema.oauth_server import (
    OAuthApproveRequest,
    OAuthApproveResponse,
    OAuthConsentInfo,
    OAuthTokenResponse,
    OAuthUserinfo,
    OIDCDiscovery,
)

oauth_router = APIRouter(prefix="/oauth2", tags=["oauth2"])

_CODE_TTL = timedelta(minutes=10)
_TOKEN_TTL = timedelta(hours=1)

_SCOPE_DESCRIPTIONS = {
    "openid": "Identify you with a unique user ID",
    "profile": "Read your username",
    "email": "Read your email address",
    "roles": "Read your platform role (admin / moderator / user)",
}

_CODE_PREFIX = "oauth:code:"
_TOKEN_PREFIX = "oauth:token:"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _get_active_client(
    session: AsyncSession, client_id: str
) -> OAuthServerClient:
    client = await crud.OAuthServerClientCrud.first(
        session=session,
        filters=[OAuthServerClient.client_id == client_id],
    )
    if not client or not client.is_active:
        raise HTTPException(400, "invalid_client")
    return client


@oauth_router.get("/.well-known/openid-configuration")
async def discovery() -> OIDCDiscovery:
    base = f"{settings.BACKEND_HOST}{settings.API_V1_STR}/oauth2"
    return OIDCDiscovery(
        issuer=settings.BACKEND_HOST,
        authorization_endpoint=f"{base}/authorize",
        token_endpoint=f"{base}/token",
        userinfo_endpoint=f"{base}/userinfo",
        scopes_supported=list(_SCOPE_DESCRIPTIONS),
        response_types_supported=["code"],
        grant_types_supported=["authorization_code"],
        token_endpoint_auth_methods_supported=["client_secret_post"],
    )


@oauth_router.get("/authorize")
async def authorize(
    session: SessionDep,
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "openid profile",
    state: str | None = None,
) -> RedirectResponse:
    if response_type != "code":
        raise HTTPException(400, "unsupported_response_type")

    client = await _get_active_client(session, client_id)

    if redirect_uri not in client.redirect_uri_list:
        raise HTTPException(400, "invalid_redirect_uri")

    qs = {"client_id": client_id, "redirect_uri": redirect_uri, "scope": scope}
    if state:
        qs["state"] = state

    return RedirectResponse(
        url=f"{settings.FRONTEND_HOST}/oauth/consent?{urlencode(qs, quote_via=quote)}",
        status_code=302,
    )


@oauth_router.get("/client-info")
async def client_info(
    session: SessionDep,
    client_id: str,
    user: CurrentUserDep,
    scope: str = "openid profile",
) -> Response[OAuthConsentInfo]:
    client = await _get_active_client(session, client_id)
    requested = [s for s in scope.split() if s in _SCOPE_DESCRIPTIONS]
    return Response(
        data=OAuthConsentInfo(
            client_id=client.client_id,
            client_name=client.name,
            client_description=client.description,
            requested_scopes=requested,
            username=user.username,
        )
    )


@oauth_router.post("/authorize/approve")
async def approve(
    session: SessionDep,
    redis: RedisDep,
    obj: OAuthApproveRequest,
    user: CurrentUserDep,
) -> Response[OAuthApproveResponse]:
    client = await _get_active_client(session, obj.client_id)

    if obj.redirect_uri not in client.redirect_uri_list:
        raise HTTPException(400, "invalid_redirect_uri")

    requested = set(obj.scope.split())
    granted = requested & set(client.allowed_scope_list)
    granted_scope = " ".join(sorted(granted))

    code = secrets.token_urlsafe(32)
    payload = json.dumps(
        {
            "client_id": obj.client_id,
            "user_id": str(user.id),
            "redirect_uri": obj.redirect_uri,
            "scopes": granted_scope,
            "state": obj.state,
        }
    )
    await redis.setex(_CODE_PREFIX + code, int(_CODE_TTL.total_seconds()), payload)

    redirect_url = f"{obj.redirect_uri}?code={code}"
    if obj.state:
        redirect_url += f"&state={obj.state}"

    return Response(data=OAuthApproveResponse(redirect_to=redirect_url))


@oauth_router.post("/token")
async def token(
    session: SessionDep,
    redis: RedisDep,
    grant_type: Annotated[str, Form()],
    code: Annotated[str, Form()],
    redirect_uri: Annotated[str, Form()],
    client_id: Annotated[str, Form()],
    client_secret: Annotated[str, Form()],
) -> OAuthTokenResponse:
    if grant_type != "authorization_code":
        raise HTTPException(400, "unsupported_grant_type")

    client = await _get_active_client(session, client_id)
    if not hmac.compare_digest(client.client_secret_hash, _hash(client_secret)):
        raise HTTPException(401, "invalid_client")

    raw_payload = await redis.get(_CODE_PREFIX + code)
    if raw_payload is None:
        raise HTTPException(400, "invalid_grant")

    data = json.loads(raw_payload)

    if data["client_id"] != client_id or data["redirect_uri"] != redirect_uri:
        raise HTTPException(400, "invalid_grant")

    # One-time use: delete the code immediately
    await redis.delete(_CODE_PREFIX + code)

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash(raw_token)
    token_payload = json.dumps(
        {
            "client_id": client_id,
            "user_id": data["user_id"],
            "scopes": data["scopes"],
        }
    )
    await redis.setex(
        _TOKEN_PREFIX + token_hash,
        int(_TOKEN_TTL.total_seconds()),
        token_payload,
    )

    return OAuthTokenResponse(
        access_token=raw_token,
        expires_in=int(_TOKEN_TTL.total_seconds()),
        scope=data["scopes"],
    )


@oauth_router.get("/userinfo")
async def userinfo(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
) -> OAuthUserinfo:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "invalid_token")

    token_hash = _hash(auth_header[7:])
    raw_payload = await redis.get(_TOKEN_PREFIX + token_hash)
    if raw_payload is None:
        raise HTTPException(401, "invalid_token")

    data = json.loads(raw_payload)

    user = await crud.UserCrud.first(
        session=session, filters=[User.id == UUID(data["user_id"])]
    )

    if not user or not user.is_active:
        raise HTTPException(401, "invalid_token")

    scopes = set(data["scopes"].split())

    return OAuthUserinfo(
        sub=str(user.id),
        username=user.username if "profile" in scopes else None,
        email=user.email if "email" in scopes else None,
        role=user.role.value if "roles" in scopes else None,
    )
