from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .question import Hint
    from .user import Team


class HintUnlock(Base):
    """A hint bought by a team; the whole team shares it and pays once."""

    __tablename__ = "hint_unlocks"
    __table_args__ = (UniqueConstraint("team_id", "hint_id", name="uq_hint_unlock"),)

    team_id: Mapped[UUID] = mapped_column(ForeignKey("teams.id"))
    hint_id: Mapped[UUID] = mapped_column(ForeignKey("hints.id"))
    cost_paid: Mapped[int]

    team: Mapped[Team] = relationship()
    hint: Mapped[Hint] = relationship()
