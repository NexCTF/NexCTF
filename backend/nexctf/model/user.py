from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .custom_field import CustomFieldValue
    from .oauth import OAuthAccount
    from .submission import ScoreAdjustment, Submission


class UserRole(enum.Enum):
    admin = "admin"
    moderator = "moderator"
    user = "user"


class Team(Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(unique=True, index=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    bracket: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    links: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    invite_code: Mapped[str | None] = mapped_column(
        String(16), unique=True, index=True, nullable=True
    )

    users: Mapped[list["User"]] = relationship(back_populates="team")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="team")
    score_adjustments: Mapped[list["ScoreAdjustment"]] = relationship(
        back_populates="team"
    )
    custom_field_values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str | None] = mapped_column(unique=True, index=True, nullable=True)
    email_verified: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    hashed_password: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    totp_secret: Mapped[str | None]
    session_version: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    links: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    @property
    def totp_enabled(self) -> bool:
        return self.totp_secret is not None

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(back_populates="user")
    tokens: Mapped[list["UserToken"]] = relationship(back_populates="user")
    custom_field_values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    team: Mapped["Team | None"] = relationship(back_populates="users")
    team_id: Mapped[UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team is not None else None


class UserToken(Base):
    """API tokens for a user (multiple allowed)."""

    __tablename__ = "user_tokens"

    name: Mapped[str | None]
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    expires_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="tokens")
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
