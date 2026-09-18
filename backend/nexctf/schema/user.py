from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import EmailStr

from nexctf.model import UserRole
from nexctf.schema.custom_field import AdminCustomFieldValueRead, EditableCustomField
from nexctf.schema.team import Link, LinkListInput


class AdminUserUpdate(PydanticBase):
    id: UUID
    username: str | None = None
    email: str | None = None
    is_active: bool | None = None
    role: UserRole | None = None
    team_id: UUID | None = None
    links: LinkListInput | None = None


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
    captcha_token: str | None = None


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


class AdminUserIpRead(PydanticBase):
    ip: str | None
    last_ip: str | None


class AdminUserDetailRead(PublicUserRead):
    # Addresses the account is reached from, most recently active first
    ips: list[AdminUserIpRead] = []
    last_login_at: datetime | None = None
    custom_field_values: list[AdminCustomFieldValueRead] = []


class PublicApiTokenCreate(PydanticBase):
    name: str | None = None
    expires_at: datetime | None = None
    scopes: list[str]


class PublicApiTokenRead(PydanticBase):
    id: UUID
    name: str | None
    expires_at: datetime | None
    scopes: list[str]
    created_at: datetime
    # Only populated on creation
    token: str | None = None


class UserSessionRead(PydanticBase):
    id: UUID
    ip: str | None
    last_ip: str | None
    user_agent: str | None
    last_seen_at: datetime
    # True for the session making the request
    current: bool


class AdminAddressAccountRead(PydanticBase):
    user_id: UUID
    username: str
    team_id: UUID | None
    team_name: str | None
    session_count: int
    last_seen_at: datetime
    user_agent: str | None
    # True when a session was opened from this address, not merely reached it
    opened_here: bool


class AdminSharedAddressRead(PydanticBase):
    ip: str
    account_count: int
    session_count: int
    # True when every account on the address belongs to one team
    same_team: bool
    # Distinct teams on the address, teamless accounts excluded
    team_count: int
    last_seen_at: datetime
    accounts: list[AdminAddressAccountRead]


class AdminSessionOverviewRead(PydanticBase):
    # Totals cover the whole window, not only the listed addresses
    session_count: int
    account_count: int
    address_count: int
    shared_address_count: int
    cross_team_address_count: int
    addresses: list[AdminSharedAddressRead]


class AdminFailedLoginUsernameRead(PydanticBase):
    username: str
    # Set when the attempted username matched an account
    user_id: UUID | None
    attempt_count: int
    last_attempt_at: datetime


class AdminFailedLoginAddressRead(PydanticBase):
    ip: str
    attempt_count: int
    # Distinct usernames tried from the address
    username_count: int
    # Of those, the ones that matched an account
    known_username_count: int
    last_attempt_at: datetime
    usernames: list[AdminFailedLoginUsernameRead]


class AdminFailedLoginOverviewRead(PydanticBase):
    # Totals cover the whole window, not only the listed addresses
    attempt_count: int
    address_count: int
    # Addresses where more than one username was tried
    spray_address_count: int
    addresses: list[AdminFailedLoginAddressRead]


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
    scopes: list[str] = []


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


class MyProfileUpdate(PydanticBase):
    """Full replacement of the user fields a player may edit."""

    links: LinkListInput = []
    custom_fields: dict[UUID, str | None] = {}


class MyProfileRead(PydanticBase):
    links: list[Link] = []
    custom_fields: list[EditableCustomField] = []
