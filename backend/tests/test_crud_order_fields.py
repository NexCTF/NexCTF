"""Every crud exposes `created_at` as a sort column, and every order field sorts."""

import inspect

import pytest
from fastapi_toolsets.crud import AsyncCrud
from fastapi_toolsets.crud.search import facet_keys
from fastapi_toolsets.types import OrderFieldType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf import crud

CRUDS = [
    obj
    for _, obj in inspect.getmembers(crud, inspect.isclass)
    if issubclass(obj, AsyncCrud) and getattr(obj, "model", None) is not None
]
ORDER_FIELDS = [
    pytest.param(c, f, id=f"{c.__name__}-{key}")
    for c in CRUDS
    for f, key in zip(c.order_fields or (), facet_keys(c.order_fields or ()))
]


@pytest.mark.parametrize("crud_cls", CRUDS, ids=lambda c: c.__name__)
def test_created_at_is_orderable(crud_cls: type[AsyncCrud]) -> None:
    columns = crud_cls._resolve_order_columns(None)
    if columns is None:
        pytest.skip("ordering disabled")
    assert "created_at" in columns


@pytest.mark.parametrize(("crud_cls", "field"), ORDER_FIELDS)
async def test_order_field_builds_valid_query(
    db_session: AsyncSession, crud_cls: type[AsyncCrud], field: OrderFieldType
) -> None:
    q = select(crud_cls.model)
    if isinstance(field, tuple):
        for rel in field[:-1]:
            q = q.outerjoin(rel)
        column = field[-1]
    else:
        column = field
    await db_session.execute(q.order_by(column.desc()).limit(1))
