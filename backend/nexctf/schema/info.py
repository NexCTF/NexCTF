from fastapi_toolsets.schemas import PydanticBase

from nexctf.schema.link import PublicLinkRead
from nexctf.schema.oauth import PublicOAuthProviderRead


class BrandingInfo(PydanticBase):
    name: str
    logo_url: str
    favicon_url: str
    primary_color: str


class CompetitionInfo(PydanticBase):
    description: str
    start_time: str
    end_time: str
    freeze_time: str
    allow_registration: bool
    allow_team_creation: bool
    # Defaulted so an `info:public` payload cached before this field existed still
    # deserializes during a rolling deploy instead of 500-ing the landing page.
    require_email: bool = False
    team_size: int


class CaptchaInfo(PydanticBase):
    enabled: bool
    widget_endpoint: str


class PublicInfo(PydanticBase):
    branding: BrandingInfo
    competition: CompetitionInfo
    oauth_providers: list[PublicOAuthProviderRead]
    captcha: CaptchaInfo
    links: list[PublicLinkRead]


class VersionInfo(PydanticBase):
    current: str
    latest: str | None = None
    release_url: str | None = None
    update_available: bool = False


class AdminStats(PydanticBase):
    users: int
    teams: int
    challenges: int
    submissions: int
    correct_submissions: int
    hint_unlocks: int
    hint_cost_spent: int
    version: VersionInfo
