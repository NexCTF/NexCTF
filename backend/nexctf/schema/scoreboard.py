from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


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
    solves: list[PublicSolveDetail]
    adjustments: list[PublicAdjustmentDetail]
    computed_at: datetime


class PublicScoreboardEntry(PydanticBase):
    rank: int
    team_id: UUID
    team_name: str
    total: int


class AdminScoreboardEntry(PydanticBase):
    rank: int
    team_id: UUID
    team_name: str
    total: int
    solve_points: int
    adjustment_points: int
    solve_count: int
    last_solve_at: datetime | None


class PublicScoreboard(PydanticBase):
    entries: list[PublicScoreboardEntry]
    computed_at: datetime


class AdminScoreboard(PydanticBase):
    entries: list[AdminScoreboardEntry]
    computed_at: datetime


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
