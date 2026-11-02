from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase
from pydantic import computed_field

# CSV export columns read straight off AdminScoreboardEntry, in export order
EXPORT_FIXED_COLUMNS = (
    "rank",
    "team_name",
    "team_bracket",
    "total",
    "solve_points",
    "hint_points",
    "adjustment_points",
    "solve_count",
    "last_solve_at",
)
# Prefix of the CSV export column for a scoreboard custom field
CUSTOM_COLUMN_PREFIX = "custom."


class PublicSolveDetail(PydanticBase):
    submission_id: UUID
    question_id: UUID
    question_label: str
    challenge_id: UUID
    challenge_title: str
    points_earned: int
    wrong_attempts: int
    solved_at: datetime


class PublicAdjustmentDetail(PydanticBase):
    id: UUID
    amount: int
    reason: str
    challenge_id: UUID | None
    challenge_title: str | None
    applied_at: datetime


class PublicTeamScoreDetail(PydanticBase):
    team_id: UUID
    team_name: str
    total: int
    solve_points: int
    adjustment_points: int
    hint_points: int
    solves: list[PublicSolveDetail]
    adjustments: list[PublicAdjustmentDetail]
    computed_at: datetime


class ScoreboardCustomField(PydanticBase):
    name: str
    label: str


class PublicScoreboardEntry(PydanticBase):
    rank: int
    team_id: UUID
    team_name: str
    team_bracket: str | None
    total: int
    custom_fields: dict[str, str] = {}


class AdminScoreboardEntry(PydanticBase):
    rank: int
    team_id: UUID
    team_name: str
    team_bracket: str | None
    total: int
    solve_points: int
    adjustment_points: int
    hint_points: int
    solve_count: int
    last_solve_at: datetime | None
    custom_fields: dict[str, str] = {}


class PublicScoreboard(PydanticBase):
    entries: list[PublicScoreboardEntry]
    computed_at: datetime
    brackets: list[str] = []
    custom_fields: list[ScoreboardCustomField] = []


class AdminScoreboard(PydanticBase):
    entries: list[AdminScoreboardEntry]
    computed_at: datetime
    brackets: list[str] = []
    custom_fields: list[ScoreboardCustomField] = []

    @computed_field
    @property
    def export_columns(self) -> list[str]:
        """Every CSV export column id, fixed columns first."""
        custom = [f"{CUSTOM_COLUMN_PREFIX}{f.name}" for f in self.custom_fields]
        return [*EXPORT_FIXED_COLUMNS, *custom]


class ScoreEvent(PydanticBase):
    ts: datetime
    cumulative: int


class TeamScoreSeries(PydanticBase):
    team_id: UUID
    team_name: str
    rank: int
    events: list[ScoreEvent]


class ScoreboardHistory(PydanticBase):
    series: list[TeamScoreSeries]
    computed_at: datetime
