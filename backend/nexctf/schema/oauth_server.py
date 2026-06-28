from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, computed_field

from nexctf.core.config import settings


class AdminOAuthClientRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str | None
    client_id: str
    redirect_uris: str
    allowed_scopes: str
    is_active: bool
    created_at: datetime

    @computed_field
    @property
    def endpoints(self) -> dict[str, str]:
        base = f"{settings.BACKEND_HOST}{settings.API_V1_STR}/oauth2"
        return {
            "metadata": f"{base}/.well-known/oauth-authorization-server",
            "authorize": f"{base}/authorize",
            "token": f"{base}/token",
            "userinfo": f"{base}/userinfo",
        }


class AdminOAuthClientCreate(BaseModel):
    name: str
    description: str | None = None
    redirect_uris: str
    allowed_scopes: str = "openid profile email roles"
    is_active: bool = True


class AdminOAuthClientCreateFull(BaseModel):
    """Internal schema — includes server-generated fields passed to CRUD."""

    model_config = {"from_attributes": True}

    name: str
    description: str | None = None
    client_id: str
    client_secret_hash: str
    redirect_uris: str
    allowed_scopes: str
    is_active: bool


class AdminOAuthClientUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    redirect_uris: str | None = None
    allowed_scopes: str | None = None
    is_active: bool | None = None


class AdminOAuthClientCreated(AdminOAuthClientRead):
    """Returned once at creation — includes the raw client_secret (shown once)."""

    client_secret: str


class OAuthServerMetadata(BaseModel):
    """RFC 8414 OAuth 2.0 Authorization Server Metadata."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    scopes_supported: list[str]
    response_types_supported: list[str]
    grant_types_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]
    code_challenge_methods_supported: list[str]


class OAuthApproveResponse(BaseModel):
    redirect_to: str


class OAuthConsentInfo(BaseModel):
    client_id: str
    client_name: str
    client_description: str | None
    requested_scopes: list[str]
    username: str


class OAuthApproveRequest(BaseModel):
    client_id: str
    redirect_uri: str
    scope: str = "openid profile"
    state: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str | None = None


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scope: str


class OAuthUserinfo(BaseModel):
    sub: str
    username: str | None = None
    email: str | None = None
    role: str | None = None
