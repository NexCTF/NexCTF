from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, Enum as SAEnum, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexctf.enums import InputType
from .base import Base

if TYPE_CHECKING:
    from .challenge import Challenge
    from .file import File
    from .solution import Solution
    from .tag import Tag

question_files_table = Table(
    "question_files",
    Base.metadata,
    Column(
        "question_id",
        PG_UUID(as_uuid=True),
        ForeignKey("questions.id"),
        primary_key=True,
    ),
    Column(
        "file_id",
        PG_UUID(as_uuid=True),
        ForeignKey("stored_files.id"),
        primary_key=True,
    ),
)

question_tags_table = Table(
    "question_tags",
    Base.metadata,
    Column(
        "question_id",
        PG_UUID(as_uuid=True),
        ForeignKey("questions.id"),
        primary_key=True,
    ),
    Column("tag_id", PG_UUID(as_uuid=True), ForeignKey("tag.id"), primary_key=True),
)


class Question(Base):
    __tablename__ = "questions"

    label: Mapped[str]
    description: Mapped[str | None]
    index: Mapped[int] = mapped_column(default=0)
    points: Mapped[int] = mapped_column(default=100)
    malus: Mapped[int | None]
    input_type: Mapped[InputType] = mapped_column(
        SAEnum(InputType, native_enum=False),
        default=InputType.INPUT,
    )

    hints: Mapped[list["Hint"]] = relationship(back_populates="question")
    solutions: Mapped[list["Solution"]] = relationship(back_populates="question")
    files: Mapped[list["File"]] = relationship(secondary=question_files_table)
    tags: Mapped[list["Tag"]] = relationship(secondary=question_tags_table)

    challenge: Mapped["Challenge"] = relationship(back_populates="questions")
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("challenges.id"))

    @property
    def challenge_title(self) -> str | None:
        return self.challenge.title if self.challenge is not None else None

    @property
    def hint_count(self) -> int:
        return len(self.hints)

    @property
    def solution_count(self) -> int:
        return len(self.solutions)

    @property
    def file_count(self) -> int:
        return len(self.files)


class Hint(Base):
    __tablename__ = "hints"

    title: Mapped[str]
    content: Mapped[str]
    cost: Mapped[int] = mapped_column(default=0)
    order: Mapped[int] = mapped_column(default=0)

    question: Mapped["Question"] = relationship(back_populates="hints")
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"))

    @property
    def question_label(self) -> str | None:
        return self.question.label if self.question is not None else None
