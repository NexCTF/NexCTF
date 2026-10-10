"""Removing challenges, questions and hints without breaking the solve history."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any
from uuid import UUID

from fastapi_toolsets.exceptions import ConflictError
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import (
    ChallengeFeedback,
    Hint,
    HintUnlock,
    Question,
    ScoreAdjustment,
    Submission,
)

_Check = tuple[Select[UUID, int], str]


async def challenge_history(
    session: AsyncSession, challenge_ids: Collection[UUID]
) -> dict[UUID, str]:
    """Why each challenge cannot be removed: the solve history referencing it."""
    if not challenge_ids:
        return {}
    key = Question.challenge_id
    return await _first_reasons(
        session,
        [
            *_question_checks(
                key,
                challenge_ids,
                "this challenge's questions",
                "this challenge's hints",
            ),
            (
                _count_by(
                    ChallengeFeedback.challenge_id, ChallengeFeedback.id, challenge_ids
                ),
                "{count} feedback row(s) reference this challenge",
            ),
            (
                _count_by(
                    ScoreAdjustment.challenge_id, ScoreAdjustment.id, challenge_ids
                ),
                "{count} score adjustment row(s) reference this challenge",
            ),
        ],
    )


async def question_history(
    session: AsyncSession, question_ids: Collection[UUID]
) -> dict[UUID, str]:
    """Why each question cannot be removed: the solve history referencing it."""
    if not question_ids:
        return {}
    return await _first_reasons(
        session,
        _question_checks(
            Question.id, question_ids, "this question", "this question's hints"
        ),
    )


async def hint_history(
    session: AsyncSession, hint_ids: Collection[UUID]
) -> dict[UUID, str]:
    """Why each hint cannot be removed: the teams that unlocked it."""
    if not hint_ids:
        return {}
    return await _first_reasons(
        session,
        [
            (
                _count_by(HintUnlock.hint_id, HintUnlock.id, hint_ids),
                "{count} team(s) unlocked this hint",
            )
        ],
    )


async def ensure_challenge_removable(session: AsyncSession, challenge_id: UUID) -> None:
    """Refuse with a 409 when solve history references the challenge."""
    if reason := (await challenge_history(session, [challenge_id])).get(challenge_id):
        raise _conflict("Challenge", f"{reason}. Deactivate the challenge instead")


async def ensure_question_removable(session: AsyncSession, question_id: UUID) -> None:
    """Refuse with a 409 when solve history references the question."""
    if reason := (await question_history(session, [question_id])).get(question_id):
        raise _conflict("Question", reason)


async def ensure_hint_removable(session: AsyncSession, hint_id: UUID) -> None:
    """Refuse with a 409 when a team unlocked the hint."""
    if reason := (await hint_history(session, [hint_id])).get(hint_id):
        raise _conflict("Hint", reason)


def _conflict(entity: str, reason: str) -> ConflictError:
    return ConflictError(
        detail=f"{entity} has solve history", desc=f"Cannot delete: {reason}."
    )


def _question_checks(
    key: Any, ids: Collection[UUID], questions: str, hints: str
) -> list[_Check]:
    """Submissions and hint unlocks under questions, grouped by *key*."""
    return [
        (
            _count_by(key, Submission.id, ids).join(
                Submission, Submission.question_id == Question.id
            ),
            f"{{count}} submission(s) reference {questions}",
        ),
        (
            _count_by(key, HintUnlock.id, ids)
            .join(Hint, Hint.question_id == Question.id)
            .join(HintUnlock, HintUnlock.hint_id == Hint.id),
            f"{{count}} team(s) unlocked {hints}",
        ),
    ]


def _count_by(key: Any, counted: Any, ids: Collection[UUID]) -> Select[UUID, int]:
    """``SELECT key, count(counted)`` for the rows whose *key* is in *ids*."""
    return select(key, func.count(counted)).where(key.in_(ids)).group_by(key)


async def _first_reasons(
    session: AsyncSession, checks: list[_Check]
) -> dict[UUID, str]:
    """Run each (id, count) query; an id keeps the reason of its first hit."""
    reasons: dict[UUID, str] = {}
    for stmt, template in checks:
        for entity_id, count in await session.execute(stmt):
            reasons.setdefault(entity_id, template.format(count=count))
    return reasons
