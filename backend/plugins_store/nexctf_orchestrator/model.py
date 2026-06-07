from __future__ import annotations

from uuid import UUID

from nexctf.model.challenge import Challenge
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class OrchestratorChallenge(Challenge):
    """Orchestrator-backed challenge."""

    __tablename__ = "challenges_orchestrator"
    __mapper_args__ = {"polymorphic_identity": "orchestrator"}

    id: Mapped[UUID] = mapped_column(ForeignKey("challenges.id"), primary_key=True)
    orchestrator_id: Mapped[UUID]
