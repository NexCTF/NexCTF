from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OAuthServerClient(Base):
    """OAuth2 authorization server — registered third-party applications."""

    __tablename__ = "oauth_server_clients"

    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[str] = mapped_column(unique=True, index=True)
    client_secret_hash: Mapped[str]
    # Newline-separated list of allowed redirect URIs
    redirect_uris: Mapped[str] = mapped_column(Text)
    # Space-separated allowed scopes e.g. "openid profile email roles"
    allowed_scopes: Mapped[str] = mapped_column(default="openid profile email")
    is_active: Mapped[bool] = mapped_column(default=True)

    @property
    def redirect_uri_list(self) -> list[str]:
        return [u.strip() for u in self.redirect_uris.splitlines() if u.strip()]

    @property
    def allowed_scope_list(self) -> list[str]:
        return self.allowed_scopes.split()
