"""CRUD base shared by every model's CRUD class."""

from typing import Any

from fastapi_toolsets.crud import AsyncCrud
from fastapi_toolsets.types import ModelType
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


def _without_id(obj: BaseModel) -> BaseModel:
    """A copy of *obj* whose ``id`` counts as unset, so an update skips it."""
    if "id" not in obj.model_fields_set:
        return obj
    copy = obj.model_copy()
    copy.__pydantic_fields_set__.discard("id")
    return copy


class Crud(AsyncCrud[ModelType]):
    """``AsyncCrud`` whose updates never rewrite the primary key."""

    @classmethod
    async def update(
        cls,
        session: AsyncSession,
        obj: BaseModel,
        filters: list[Any],
        *,
        exclude_unset: bool = True,
        exclude_none: bool = False,
        with_for_update: Any = False,
        schema: type[BaseModel] | None = None,
    ) -> Any:
        return await super().update(
            session,
            _without_id(obj),
            filters,
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
            with_for_update=with_for_update,
            schema=schema,
        )
