from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .question import Hint, Question
    from .tag import Tag
    from .user import User

challenge_tags_table = Table(
    "challenge_tags",
    Base.metadata,
    Column(
        "challenge_id",
        PG_UUID(as_uuid=True),
        ForeignKey("challenges.id"),
        primary_key=True,
    ),
    Column("tag_id", PG_UUID(as_uuid=True), ForeignKey("tag.id"), primary_key=True),
)


class ChallengeCategory(Base):
    __tablename__ = "challenge_categories"

    slug: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]

    challenges: Mapped[list["Challenge"]] = relationship(back_populates="category")


class Challenge(Base):
    __tablename__ = "challenges"
    __mapper_args__ = {"polymorphic_on": "challenge_type"}

    challenge_type: Mapped[str] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=False)
    sequential: Mapped[bool] = mapped_column(default=False)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="challenge", order_by="Question.index"
    )

    category: Mapped["ChallengeCategory | None"] = relationship(
        back_populates="challenges"
    )
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("challenge_categories.id"), nullable=True
    )

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category is not None else None

    @property
    def question_count(self) -> int:
        return len(self.questions)

    tags: Mapped[list["Tag"]] = relationship(secondary=challenge_tags_table)

    author: Mapped["User | None"] = relationship()
    author_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    async def on_start(self, user: User) -> None:
        """Called when a user opens the challenge (e.g. provision a container)."""
        logger.info(
            "challenge.start type=%s challenge=%s user=%s",
            self.challenge_type,
            self.id,
            user.id,
        )

    async def on_submit(self, user: User, question: Question, submission: str) -> None:
        """Called on every flag submission, before the result is determined."""
        logger.info(
            "challenge.submit type=%s challenge=%s question=%s user=%s",
            self.challenge_type,
            self.id,
            question.id,
            user.id,
        )

    async def on_solve(self, user: User, question: Question) -> None:
        """Called when a user submits a correct flag for a question."""
        logger.info(
            "challenge.solve type=%s challenge=%s question=%s user=%s points=%s",
            self.challenge_type,
            self.id,
            question.id,
            user.id,
            question.points,
        )

    async def on_fail(self, user: User, question: Question, submission: str) -> None:
        """Called when a user submits a wrong flag for a question."""
        logger.info(
            "challenge.fail type=%s challenge=%s question=%s user=%s malus=%s",
            self.challenge_type,
            self.id,
            question.id,
            user.id,
            question.malus,
        )

    async def on_complete(self, user: User) -> None:
        """Called when a user has solved all questions in the challenge."""
        logger.info(
            "challenge.complete type=%s challenge=%s user=%s",
            self.challenge_type,
            self.id,
            user.id,
        )

    async def on_hint_unlock(self, user: User, hint: Hint) -> None:
        """Called when a user unlocks a hint."""
        logger.info(
            "challenge.hint_unlock type=%s challenge=%s hint=%s user=%s cost=%s",
            self.challenge_type,
            self.id,
            hint.id,
            user.id,
            hint.cost,
        )

    async def on_stop(self, user: User) -> None:
        """Called when a challenge session ends (e.g. tear down a container)."""
        logger.info(
            "challenge.stop type=%s challenge=%s user=%s",
            self.challenge_type,
            self.id,
            user.id,
        )
