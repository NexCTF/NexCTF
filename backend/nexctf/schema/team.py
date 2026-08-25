from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import Field

from nexctf.schema.custom_field import (
    AdminCustomFieldValueRead,
    EditableCustomField,
    PublicCustomFieldValue,
)
from nexctf.schema.stats import TeamChallengeStats
from nexctf.util.pydantic import Label

# ISO 3166-1 alpha-2: exactly two uppercase letters
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class Link(PydanticBase):
    label: str
    url: str


class LinkInput(Link):
    """A link accepted from a client: http(s) only, so no ``javascript:`` hrefs."""

    label: Annotated[str, Field(max_length=64)]
    url: Annotated[str, Field(pattern=r"^https?://", max_length=512)]


LinkListInput = Annotated[list[LinkInput], Field(max_length=10)]


class TeamCreate(PydanticBase):
    name: str


class AdminTeamCreate(PydanticBase):
    name: str
    country: CountryCode | None = None
    bracket: Label = None
    links: LinkListInput = []


class AdminTeamCreateRequest(AdminTeamCreate):
    custom_fields: dict[UUID, str | None] = {}


class AdminTeamUpdate(PydanticBase):
    id: UUID
    name: str | None = None
    country: CountryCode | None = None
    bracket: Label = None
    links: LinkListInput | None = None


class AdminTeamRead(PydanticBase):
    id: UUID
    name: str
    country: str | None = None
    bracket: str | None = None
    links: list[Link] = []


class AdminTeamMember(PydanticBase):
    id: UUID
    username: str
    email: str | None
    role: str
    is_active: bool


class AdminTeamDetailRead(AdminTeamRead):
    invite_code: str
    created_at: datetime
    updated_at: datetime
    users: list[AdminTeamMember]
    custom_field_values: list[AdminCustomFieldValueRead] = []


class PublicTeamMember(PydanticBase):
    id: UUID
    username: str
    links: list[Link] = []
    custom_fields: list[PublicCustomFieldValue] = []


class PublicTeamRead(PydanticBase):
    id: UUID
    name: str
    country: str | None
    bracket: str | None
    links: list[Link] = []
    members: list[PublicTeamMember] | None
    member_count: int
    challenge_stats: list[TeamChallengeStats]
    custom_fields: list[PublicCustomFieldValue] = []
    rank: int | None = None
    score: int | None = None
    team_count: int = 0


class MyTeamRead(PublicTeamRead):
    invite_code: str


class TeamJoinRequest(PydanticBase):
    code: str


class MyTeamProfileUpdate(PydanticBase):
    """Full replacement of the team fields a member may edit."""

    name: str
    country: CountryCode | None = None
    links: LinkListInput = []
    custom_fields: dict[UUID, str | None] = {}


class MyTeamProfileRead(PydanticBase):
    name: str
    country: str | None
    links: list[Link] = []
    custom_fields: list[EditableCustomField] = []
