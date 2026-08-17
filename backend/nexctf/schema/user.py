from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import EmailStr

from nexctf.model import UserRole
from nexctf.schema.custom_field import AdminCustomFieldValueRead
from nexctf.schema.team import Link


class AdminUserUpdate(PydanticBase):
    id: UUID
    username: str | None = None
    email: str | None = None
    is_active: bool | None = None
    role: UserRole | None = None
    team_id: UUID | None = None
    links: list[Link] | None = None


class AdminUserCreate(PydanticBase):
    username: str
    password: str
    email: EmailStr | None = None
    role: UserRole = UserRole.user
    team_id: UUID | None = None
    custom_fields: dict[UUID, str | None] = {}


class PublicRegisterRequest(PydanticBase):
    username: str
    password: str
    email: EmailStr | None = None
    cap_token: str | None = None


class PublicUserRead(PydanticBase):
    id: UUID
    username: str
    email: str | None
    email_verified: bool = False
    role: str
    is_active: bool
    team_id: UUID | None = None
    team_name: str | None = None
    totp_enabled: bool = False
    has_password: bool = False
    links: list[Link] = []


class AdminUserDetailRead(PublicUserRead):
    last_login_ip: str | None = None
    last_login_at: datetime | None = None
    custom_field_values: list[AdminCustomFieldValueRead] = []


class PublicApiTokenCreate(PydanticBase):
    name: str | None = None
    expires_at: datetime | None = None


class PublicApiTokenRead(PydanticBase):
    id: UUID
    name: str | None
    expires_at: datetime | None
    created_at: datetime
    # Only populated on creation
    token: str | None = None


class PublicUserSessionRead(PydanticBase):
    id: UUID
    ip: str | None
    user_agent: str | None
    last_seen_at: datetime
    # True for the session making the request
    current: bool


class UserCreate(PydanticBase):
    username: str
    email: str | None = None
    hashed_password: str | None = None
    email_verified: bool = False
    role: UserRole = UserRole.user
    team_id: UUID | None = None


class UserTokenCreate(PydanticBase):
    user_id: UUID
    token_hash: str
    name: str | None = None
    expires_at: datetime | None = None


class UserTotpUpdate(PydanticBase):
    id: UUID | None = None
    totp_secret: str | None = None


class UserPasswordUpdate(PydanticBase):
    id: UUID | None = None
    hashed_password: str | None = None
    session_version: int | None = None


class UserTeamUpdate(PydanticBase):
    team_id: UUID | None


class PasswordResetRequest(PydanticBase):
    token: str
    new_password: str


class PasswordChangeRequest(PydanticBase):
    current_password: str
    new_password: str


class ForgotPasswordRequest(PydanticBase):
    email: EmailStr


class EmailVerifyRequest(PydanticBase):
    token: str


class ResendVerificationRequest(PydanticBase):
    email: EmailStr


class UserEmailVerifiedUpdate(PydanticBase):
    id: UUID | None = None
    email_verified: bool = True


class TotpSetupResponse(PydanticBase):
    provisioning_uri: str


class TotpEnableRequest(PydanticBase):
    code: str


class TotpDisableRequest(PydanticBase):
    code: str
