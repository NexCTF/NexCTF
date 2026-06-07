from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class QuestionStats(PydanticBase):
    question_id: UUID
    question_label: str
    question_index: int
    attempt_count: int
    correct_count: int
    teams_attempted: int
    teams_solved: int
    hint_unlock_count: int = 0
    hint_cost_spent: int = 0
    first_blood_team_name: str | None
    first_blood_at: datetime | None


class ChallengeStats(PydanticBase):
    challenge_id: UUID
    challenge_title: str
    question_count: int
    attempt_count: int
    correct_count: int
    teams_attempted: int
    teams_solved: int
    hint_unlock_count: int = 0
    hint_cost_spent: int = 0
    first_blood_team_id: UUID | None
    first_blood_team_name: str | None
    first_blood_at: datetime | None
    questions: list[QuestionStats] = []


class TeamChallengeStats(PydanticBase):
    challenge_id: UUID
    challenge_title: str
    question_count: int
    solved_question_count: int
    is_solved: bool
    attempt_count: int
    points_earned: int
    first_solve_at: datetime | None
    last_solve_at: datetime | None


class AdminTeamChallengeStats(TeamChallengeStats):
    hint_unlock_count: int = 0
    hint_cost_spent: int = 0
