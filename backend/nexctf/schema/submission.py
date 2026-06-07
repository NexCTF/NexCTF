from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminSubmissionRead(PydanticBase):
    id: UUID
    team_id: UUID
    question_id: UUID
    answer: str
    is_correct: bool
    points_earned: int
    wrong_count_before: int
    created_at: datetime
    team_name: str | None = None
    question_label: str | None = None
    question_challenge_title: str | None = None
