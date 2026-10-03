"""Challenge writes that run the type's admin lifecycle hooks in one savepoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi_toolsets.db import transaction
from sqlalchemy import inspect, select
from sqlalchemy.orm import with_polymorphic

from nexctf.model import Challenge

if TYPE_CHECKING:
    from pydantic import BaseModel
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexctf.plugins.registry import RegistryEntry

_IGNORED_COLUMNS = frozenset({"updated_at"})


def _column_values(instance: Challenge) -> dict[str, Any]:
    """Snapshot the instance's loaded column values, without loading any."""
    state = inspect(instance)
    return {
        attr.key: state.dict[attr.key]
        for attr in state.mapper.column_attrs
        if attr.key in state.dict and attr.key not in _IGNORED_COLUMNS
    }


async def load(session: AsyncSession, challenge_id: UUID) -> Challenge | None:
    """Load a challenge as its registered subclass, every column loaded."""
    polymorphic = with_polymorphic(Challenge, "*")
    result = await session.execute(
        select(polymorphic).where(polymorphic.id == challenge_id)
    )
    return result.scalar_one_or_none()


@asynccontextmanager
async def updating(
    session: AsyncSession, challenge: Challenge, obj: BaseModel
) -> AsyncIterator[None]:
    """Write the block's changes to ``challenge``, then run ``after_update``."""
    before = _column_values(challenge)
    yield
    await session.flush()
    after = _column_values(challenge)
    changed = {key for key, value in after.items() if before.get(key) != value}
    await challenge.after_update(session, obj, changed)


async def create(
    session: AsyncSession, entry: RegistryEntry, obj: BaseModel
) -> Challenge:
    """Create a challenge, then run its ``after_create`` hook."""
    async with transaction(session):
        challenge = await entry.crud.create(session=session, obj=obj)
        await challenge.after_create(session, obj)
    return challenge


async def update(
    session: AsyncSession, crud: Any, obj: BaseModel, challenge_id: UUID
) -> Challenge:
    """Update a challenge, then run its ``after_update`` hook."""
    async with transaction(session):
        challenge = await session.get_one(crud.model, challenge_id)
        async with updating(session, challenge, obj):
            challenge = await crud.update(
                session=session, obj=obj, filters=[crud.model.id == challenge_id]
            )
    return challenge


async def delete(session: AsyncSession, crud: Any, challenge_id: UUID) -> None:
    """Run a challenge's ``before_delete`` hook, then delete it."""
    async with transaction(session):
        challenge = await session.get_one(crud.model, challenge_id)
        await challenge.before_delete(session)
        await session.delete(challenge)
        await session.flush()
