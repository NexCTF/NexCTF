from .oauth import OAuthAccountCreate, PublicOAuthAccountRead, PublicOAuthProviderRead
from .scoreboard import (
    AdminScoreboard,
    AdminScoreboardEntry,
    PublicAdjustmentDetail,
    PublicScoreboard,
    PublicScoreboardEntry,
    PublicSolveDetail,
    PublicTeamScoreDetail,
    ScoreboardCustomField,
    ScoreboardHistory,
    ScoreEvent,
    TeamScoreSeries,
)
from .user import (
    PublicApiTokenCreate,
    PublicApiTokenRead,
    PublicRegisterRequest,
    PublicUserRead,
    PublicUserSessionRead,
    UserCreate,
    UserTeamUpdate,
    UserTokenCreate,
    UserTotpUpdate,
)

__all__ = [  # noqa: RUF022
    # user
    "PublicRegisterRequest",
    "PublicUserRead",
    "PublicApiTokenCreate",
    "PublicApiTokenRead",
    "PublicUserSessionRead",
    "UserCreate",
    "UserTeamUpdate",
    "UserTokenCreate",
    "UserTotpUpdate",
    # oauth
    "PublicOAuthProviderRead",
    "PublicOAuthAccountRead",
    "OAuthAccountCreate",
    # scoreboard
    "AdminScoreboard",
    "AdminScoreboardEntry",
    "PublicAdjustmentDetail",
    "PublicScoreboard",
    "PublicScoreboardEntry",
    "PublicSolveDetail",
    "PublicTeamScoreDetail",
    "ScoreboardCustomField",
    "ScoreboardHistory",
    "ScoreEvent",
    "TeamScoreSeries",
]
