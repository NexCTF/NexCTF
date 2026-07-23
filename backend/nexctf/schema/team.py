from typing import Annotated
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import Field

from nexctf.schema.custom_field import AdminCustomFieldValueRead
from nexctf.schema.stats import TeamChallengeStats

# ISO 3166-1 alpha-2: exactly two uppercase letters
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class Link(PydanticBase):
    label: str
    url: str


class TeamCreate(PydanticBase):
    name: str
    invite_code: str


class AdminTeamCreate(PydanticBase):
    name: str
    country: CountryCode | None = None
    bracket: str | None = None
    links: list[Link] = []


class AdminTeamUpdate(PydanticBase):
    id: UUID
    name: str | None = None
    country: CountryCode | None = None
    bracket: str | None = None
    links: list[Link] | None = None


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
    users: list[AdminTeamMember]
    custom_field_values: list[AdminCustomFieldValueRead] = []


class PublicTeamMember(PydanticBase):
    id: UUID
    username: str


class PublicTeamRead(PydanticBase):
    id: UUID
    name: str
    country: str | None
    bracket: str | None
    members: list[PublicTeamMember]
    challenge_stats: list[TeamChallengeStats]
    invite_code: str | None


class TeamCreateRequest(PydanticBase):
    name: str


class TeamJoinRequest(PydanticBase):
    code: str
