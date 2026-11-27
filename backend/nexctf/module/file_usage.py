"""Where stored files are used: link tables and markdown or config references."""

import re
from collections import defaultdict
from collections.abc import Collection
from uuid import UUID

from sqlalchemy import ColumnElement, Select, exists, func, literal, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.enums import FileUsageKind
from nexctf.model import (
    Challenge,
    ConfigEntry,
    CustomPage,
    File,
    Hint,
    Notification,
    Question,
)
from nexctf.model.challenge import challenge_files_table
from nexctf.model.question import question_files_table
from nexctf.schema.file import AdminFileSummary, FileUsage

Usages = dict[UUID, list[FileUsage]]

_HEX = "[0-9a-fA-F]"
_REF = re.compile(
    rf"/file/({_HEX}{{8}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{12}})/view"
)
_NULL_ID = literal(None, type_=Challenge.id.type)


def _referenced_ids(*texts: str | None) -> set[UUID]:
    return {UUID(m) for text in texts for m in _REF.findall(text or "")}


def _question_label() -> ColumnElement[str]:
    return func.concat(Challenge.title, " / ", Question.label)


def _text_sources(like: str) -> list[tuple[FileUsageKind, Select]]:
    """Each text source as ``(kind, select of target_id, label, cid, *texts)``."""
    return [
        (
            FileUsageKind.CHALLENGE_TEXT,
            select(
                Challenge.id,
                Challenge.title,
                Challenge.id,
                Challenge.description,
                Challenge.writeup,
            ).where(
                or_(Challenge.description.ilike(like), Challenge.writeup.ilike(like))
            ),
        ),
        (
            FileUsageKind.QUESTION_TEXT,
            select(Question.id, _question_label(), Challenge.id, Question.description)
            .join(Challenge, Question.challenge_id == Challenge.id)
            .where(Question.description.ilike(like)),
        ),
        (
            FileUsageKind.HINT_TEXT,
            select(
                Hint.id,
                func.concat(_question_label(), " / ", Hint.title),
                Challenge.id,
                Hint.content,
            )
            .join(Question, Hint.question_id == Question.id)
            .join(Challenge, Question.challenge_id == Challenge.id)
            .where(Hint.content.ilike(like)),
        ),
        (
            FileUsageKind.PAGE_TEXT,
            select(CustomPage.id, CustomPage.title, _NULL_ID, CustomPage.content).where(
                CustomPage.content.ilike(like)
            ),
        ),
        (
            FileUsageKind.NOTIFICATION_TEXT,
            select(
                Notification.id, Notification.title, _NULL_ID, Notification.content
            ).where(Notification.content.ilike(like)),
        ),
        (
            FileUsageKind.CONFIG,
            select(
                _NULL_ID,
                ConfigEntry.key,
                _NULL_ID,
                ConfigEntry.value,
            ).where(ConfigEntry.value.ilike(like)),
        ),
    ]


async def text_usages(session: AsyncSession, file_id: UUID | None = None) -> Usages:
    """Text references to every file, or to *file_id* only, keyed by file id."""
    like = f"%/file/{file_id or '%'}/view%"
    out: Usages = defaultdict(list)
    for kind, stmt in _text_sources(like):
        for target_id, label, challenge_id, *texts in await session.execute(stmt):
            usage = FileUsage(
                kind=kind, target_id=target_id, label=label, challenge_id=challenge_id
            )
            for found in _referenced_ids(*texts):
                out[found].append(usage)
    return out


def _link_sources(file_ids: Collection[UUID]) -> list[tuple[FileUsageKind, Select]]:
    """Each link table as ``(kind, select of file_id, target_id, label, cid)``."""
    return [
        (
            FileUsageKind.CHALLENGE,
            select(
                challenge_files_table.c.file_id,
                Challenge.id,
                Challenge.title,
                Challenge.id,
            )
            .join(Challenge, challenge_files_table.c.challenge_id == Challenge.id)
            .where(challenge_files_table.c.file_id.in_(file_ids))
            .order_by(Challenge.title),
        ),
        (
            FileUsageKind.QUESTION,
            select(
                question_files_table.c.file_id,
                Question.id,
                _question_label(),
                Challenge.id,
            )
            .join(Question, question_files_table.c.question_id == Question.id)
            .join(Challenge, Question.challenge_id == Challenge.id)
            .where(question_files_table.c.file_id.in_(file_ids))
            .order_by(Challenge.title, Question.index),
        ),
    ]


async def link_usages(session: AsyncSession, file_ids: Collection[UUID]) -> Usages:
    """Challenge and question links of *file_ids*, keyed by file id."""
    out: Usages = defaultdict(list)
    if not file_ids:
        return out
    for kind, stmt in _link_sources(file_ids):
        for file_id, target_id, label, challenge_id in await session.execute(stmt):
            out[file_id].append(
                FileUsage(
                    kind=kind,
                    target_id=target_id,
                    label=label,
                    challenge_id=challenge_id,
                )
            )
    return out


async def usages(
    session: AsyncSession, file_ids: Collection[UUID], texts: Usages
) -> Usages:
    """Links of *file_ids* followed by their text references from *texts*."""
    out = await link_usages(session, file_ids)
    for file_id in file_ids:
        out[file_id].extend(texts.get(file_id, []))
    return out


def used_clause(text_ids: Collection[UUID]) -> ColumnElement[bool]:
    """Whether a ``File`` row is linked or referenced from text."""
    return or_(
        File.id.in_(text_ids),
        exists().where(question_files_table.c.file_id == File.id),
        exists().where(challenge_files_table.c.file_id == File.id),
    )


def challenge_clause(challenge_id: UUID, texts: Usages) -> ColumnElement[bool]:
    """Whether a ``File`` row is used by *challenge_id* or one of its questions."""
    text_ids = [
        file_id
        for file_id, found in texts.items()
        if any(u.challenge_id == challenge_id for u in found)
    ]
    return or_(
        File.id.in_(text_ids),
        File.id.in_(
            select(challenge_files_table.c.file_id).where(
                challenge_files_table.c.challenge_id == challenge_id
            )
        ),
        File.id.in_(
            select(question_files_table.c.file_id)
            .join(Question, question_files_table.c.question_id == Question.id)
            .where(Question.challenge_id == challenge_id)
        ),
    )


async def summary(session: AsyncSession) -> AdminFileSummary:
    """File count, total stored size and how many files nothing uses."""
    texts = await text_usages(session)
    count, total_size, unused = (
        await session.execute(
            select(
                func.count(File.id),
                func.coalesce(func.sum(File.file_size), 0),
                func.count(File.id).filter(not_(used_clause(list(texts)))),
            )
        )
    ).one()
    return AdminFileSummary(
        count=count, total_size=int(total_size or 0), unused_count=unused
    )
