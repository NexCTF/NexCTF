from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class OAuthProvider(Base):
    """Configurable OAuth2 / OpenID Connect provider."""

    __tablename__ = "oauth_providers"

    slug: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    client_id: Mapped[str]
    client_secret: Mapped[str]
    discovery_url: Mapped[str]
    scopes: Mapped[str] = mapped_column(default="openid email profile")
    icon_url: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=True)

    accounts: Mapped[list["OAuthAccount"]] = relationship(back_populates="provider")


class OAuthAccount(Base):
    """OAuth2 / OpenID Connect account linked to a user."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider_id", "subject", name="uq_oauth_provider_subject"),
    )

    subject: Mapped[str]

    user: Mapped["User"] = relationship(back_populates="oauth_accounts")
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    provider_id: Mapped[UUID] = mapped_column(ForeignKey("oauth_providers.id"))
    provider: Mapped["OAuthProvider"] = relationship(back_populates="accounts")
