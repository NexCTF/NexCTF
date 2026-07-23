"""Compute the cacheable, user-agnostic structure of player-facing challenges.

The structures here hold every field a player view can need (including presigned
file URLs and hint content). They are server-side only; per-request assembly in
the API layer decides what is actually exposed based on the caller's solved /
unlocked / lock state.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from fastapi_toolsets.exceptions import NotFoundError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectin_polymorphic, selectinload

from nexctf.core import s3
from nexctf.enums import InputType
from nexctf.model import Challenge, Question
from nexctf.model.solution import Solution
from nexctf.plugins.registry import solution_registry
from nexctf.schema.file import PublicFileRead
from nexctf.schema.tag import PublicTagRead


class HintStructure(BaseModel):
    """A hint with its content; content is only exposed once a user unlocks it."""

    id: UUID
    title: str
    cost: int
    content: str
    order: int


class QuestionStructure(BaseModel):
    """A question with all assets resolved (files presigned, options collected)."""

    id: UUID
    label: str
    description: str | None
    points: int
    malus: int | None
    input_type: InputType
    index: int
    files: list[PublicFileRead]
    hints: list[HintStructure]
    tags: list[PublicTagRead]
    options: list[str] | None
    multi_select: bool


class ChallengeListItem(BaseModel):
    """A single challenge as shown in the list, minus per-team solved counts."""

    id: UUID
    title: str
    category_id: UUID | None
    category_name: str | None
    question_ids: list[UUID]
    tags: list[PublicTagRead]


class ChallengeDetailStructure(BaseModel):
    """A full challenge detail, minus per-user solved / locked / unlocked state."""

    id: UUID
    title: str
    description: str | None
    writeup: str | None
    category_id: UUID | None
    category_name: str | None
    challenge_type: str
    sequential: bool
    tags: list[PublicTagRead]
    questions: list[QuestionStructure]


def _tags(obj: Challenge | Question) -> list[PublicTagRead]:
    return [
        PublicTagRead(id=t.id, name=t.name, description=t.description, color=t.color)
        for t in obj.tags
    ]


def solution_load_option() -> Any:
    """Return the correct selectinload option for Question.solutions."""
    subclasses = solution_registry.polymorphic_subclasses
    if subclasses:
        return selectinload(Question.solutions).options(
            selectin_polymorphic(Solution, subclasses)
        )
    return selectinload(Question.solutions)


async def compute_list_structure(session: AsyncSession) -> list[ChallengeListItem]:
    """Build the cacheable challenge-list structure (all active challenges)."""
    result = await session.execute(
        select(Challenge)
        .where(Challenge.is_active.is_(True))
        .options(
            selectinload(Challenge.questions),
            selectinload(Challenge.category),
            selectinload(Challenge.tags),
        )
        .order_by(Challenge.title)
    )
    challenges = result.scalars().all()
    return [
        ChallengeListItem(
            id=c.id,
            title=c.title,
            category_id=c.category_id,
            category_name=c.category_name,
            question_ids=[q.id for q in c.questions],
            tags=_tags(c),
        )
        for c in challenges
    ]


async def _question_structure(q: Question) -> QuestionStructure:
    async def _presign(key: str) -> str:
        try:
            return await s3.presigned_view_url(key)  # type: ignore[attr-defined]
        except Exception:
            return ""

    urls = await asyncio.gather(*[_presign(f.s3_key) for f in q.files])
    files = [
        PublicFileRead(
            id=f.id,
            name=f.name,
            original_filename=f.original_filename,
            mime_type=f.mime_type,
            file_size=f.file_size,
            url=url,
        )
        for f, url in zip(q.files, urls)
    ]

    hints = [
        HintStructure(
            id=h.id, title=h.title, cost=h.cost, content=h.content, order=h.order
        )
        for h in sorted(q.hints, key=lambda h: h.order)
    ]

    # Collect player-facing options from solutions that expose them (e.g. MCQ).
    # The unique set is stored unshuffled; the API shuffles per request.
    all_opts: list[str] = []
    multi_select = False
    for sol in q.solutions:
        sol_opts = sol.public_options()
        if sol_opts:
            all_opts.extend(sol_opts)
        if sol.is_multi_select():
            multi_select = True
    options = list(set(all_opts)) if all_opts else None

    return QuestionStructure(
        id=q.id,
        label=q.label,
        description=q.description,
        points=q.points,
        malus=q.malus,
        input_type=q.input_type,
        index=q.index,
        files=files,
        hints=hints,
        tags=_tags(q),
        options=options,
        multi_select=multi_select,
    )


async def compute_detail_structure(
    session: AsyncSession, challenge_id: UUID
) -> ChallengeDetailStructure:
    """Build the cacheable detail structure for one active challenge.

    Raises:
        NotFoundError: if no active challenge with that id exists.
    """
    result = await session.execute(
        select(Challenge)
        .where(Challenge.id == challenge_id, Challenge.is_active.is_(True))
        .options(
            selectinload(Challenge.category),
            selectinload(Challenge.tags),
            selectinload(Challenge.questions).options(
                solution_load_option(),
                selectinload(Question.hints),
                selectinload(Question.files),
                selectinload(Question.tags),
            ),
        )
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise NotFoundError(detail="Challenge not found")

    questions = sorted(challenge.questions, key=lambda q: q.index)
    question_structs = list(
        await asyncio.gather(*[_question_structure(q) for q in questions])
    )
    return ChallengeDetailStructure(
        id=challenge.id,
        title=challenge.title,
        description=challenge.description,
        writeup=challenge.writeup,
        category_id=challenge.category_id,
        category_name=challenge.category_name,
        challenge_type=challenge.challenge_type,
        sequential=challenge.sequential,
        tags=_tags(challenge),
        questions=question_structs,
    )
