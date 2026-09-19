"""Intermediate representation of a content bundle."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FORMAT_VERSION = 1


class BundleBase(BaseModel):
    """Base for every IR node: strict about unknown keys, forbids mutation drift."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RequiresIR(BundleBase):
    """What an importing instance must have registered to accept the bundle."""

    challenge_types: list[str] = []
    solve_types: list[str] = []
    plugins: list[str] = []


class ManifestIR(BundleBase):
    """``nexctf.yaml``: the only place a volatile timestamp is allowed."""

    format_version: int = FORMAT_VERSION
    nexctf_version: str
    exported_at: datetime
    requires: RequiresIR = Field(default_factory=RequiresIR)


class HintIR(BundleBase):
    """A hint, embedded in its question."""

    id: UUID
    title: str
    content: str
    cost: int = 0
    order: int = 0


class SolutionIR(BundleBase):
    """A solution, embedded in its question. ``data`` holds the subclass columns."""

    id: UUID
    solve_type: str
    data: dict[str, Any] = {}


class QuestionIR(BundleBase):
    """A question with its hints and solutions. ``description`` lives in a sibling."""

    id: UUID
    label: str
    description: str | None = None
    index: int = 0
    points: int = 100
    malus: int | None = None
    input_type: str = "input"
    trap_flags: list[str] = []
    tags: list[str] = []
    file_ids: list[UUID] = []
    hints: list[HintIR] = []
    solutions: list[SolutionIR] = []


class ChallengeIR(BundleBase):
    """A challenge. ``data`` holds the polymorphic subclass columns."""

    id: UUID
    challenge_type: str
    title: str
    description: str | None = None
    writeup: str | None = None
    is_active: bool = False
    sequential: bool = False
    category: str | None = None
    tags: list[str] = []
    author_username: str | None = None
    data: dict[str, Any] = {}
    questions: list[QuestionIR] = []


class FileIR(BundleBase):
    """A stored file's metadata. ``s3_key`` is never serialized; import mints it."""

    id: UUID
    name: str
    original_filename: str
    mime_type: str | None = None
    file_size: int | None = None
    is_public: bool = False
    sha256: str | None = None


class PageIR(BundleBase):
    """A custom page. ``content`` is the markdown body of ``pages/<slug>.md``."""

    id: UUID
    slug: str
    title: str
    content: str = ""
    is_published: bool = False
    nav_placement: str | None = None


class LinkIR(BundleBase):
    """An external link."""

    id: UUID
    name: str
    url: str
    visibility: str
    is_enabled: bool = True


class CustomFieldIR(BundleBase):
    """A custom field definition. Values are out of scope."""

    id: UUID
    name: str
    label: str
    field_type: str
    target: str
    is_required: bool = False
    is_public: bool = True
    is_self_editable: bool = True
    show_in_scoreboard: bool = False


class Bundle(BundleBase):
    """A whole instance's authored content."""

    manifest: ManifestIR
    config: dict[str, str] = {}
    challenges: list[ChallengeIR] = []
    files: list[FileIR] = []
    pages: list[PageIR] = []
    links: list[LinkIR] = []
    custom_fields: list[CustomFieldIR] = []

    def questions(self) -> list[tuple[ChallengeIR, QuestionIR]]:
        """Every question with the challenge owning it."""
        return [(c, q) for c in self.challenges for q in c.questions]

    def solutions(self) -> list[tuple[QuestionIR, SolutionIR]]:
        """Every solution with the question owning it."""
        return [(q, s) for _, q in self.questions() for s in q.solutions]
