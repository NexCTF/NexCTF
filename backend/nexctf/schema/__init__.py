from .oauth import OAuthAccountCreate, PublicOAuthAccountRead, PublicOAuthProviderRead
from .scoreboard import (
    AdminScoreboard,
    AdminScoreboardEntry,
    PublicAdjustmentDetail,
    PublicScoreboard,
    PublicScoreboardEntry,
    PublicSolveDetail,
    PublicTeamScoreDetail,
    ScoreboardHistory,
    ScoreEvent,
    TeamScoreSeries,
)
from .user import (
    PublicApiTokenCreate,
    PublicApiTokenRead,
    PublicRegisterRequest,
    PublicUserRead,
    UserCreate,
    UserTeamUpdate,
    UserTokenCreate,
    UserTotpUpdate,
)

__all__ = [
    # user
    "PublicRegisterRequest",
    "PublicUserRead",
    "PublicApiTokenCreate",
    "PublicApiTokenRead",
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
    "ScoreboardHistory",
    "ScoreEvent",
    "TeamScoreSeries",
]
