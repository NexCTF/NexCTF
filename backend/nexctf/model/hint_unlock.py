from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .question import Hint
    from .user import User


class HintUnlock(Base):
    __tablename__ = "hint_unlocks"
    __table_args__ = (UniqueConstraint("user_id", "hint_id", name="uq_hint_unlock"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    hint_id: Mapped[UUID] = mapped_column(ForeignKey("hints.id"))
    cost_paid: Mapped[int]

    user: Mapped["User"] = relationship()
    hint: Mapped["Hint"] = relationship()
