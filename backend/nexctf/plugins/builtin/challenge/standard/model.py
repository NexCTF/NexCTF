from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from nexctf.model.challenge import Challenge


class StandardChallenge(Challenge):
    """Plain challenge — uses default lifecycle hooks from Challenge base."""

    __tablename__ = "challenges_standard"
    __mapper_args__ = {"polymorphic_identity": "standard"}

    id: Mapped[UUID] = mapped_column(ForeignKey("challenges.id"), primary_key=True)
