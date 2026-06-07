from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class PublicOAuthProviderRead(PydanticBase):
    slug: str
    name: str
    icon_url: str | None = None


class OAuthAccountCreate(PydanticBase):
    user_id: UUID
    provider_id: UUID
    subject: str


class PublicOAuthAccountRead(PydanticBase):
    id: UUID
    provider_slug: str
    provider_name: str
    provider_icon_url: str | None = None


class AdminOAuthProviderRead(PydanticBase):
    id: UUID
    slug: str
    name: str
    client_id: str
    discovery_url: str
    scopes: str
    icon_url: str | None = None
    is_active: bool


class AdminOAuthProviderCreate(PydanticBase):
    slug: str
    name: str
    client_id: str
    client_secret: str
    discovery_url: str
    scopes: str = "openid email profile"
    icon_url: str | None = None
    is_active: bool = True


class AdminOAuthProviderUpdate(PydanticBase):
    id: UUID
    slug: str | None = None
    name: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    discovery_url: str | None = None
    scopes: str | None = None
    icon_url: str | None = None
    is_active: bool | None = None
