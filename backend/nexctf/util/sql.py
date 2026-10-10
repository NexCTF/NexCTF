"""Small SQLAlchemy query helpers."""

from __future__ import annotations

from sqlalchemy import ColumnElement, ScalarSelect, func, select

from nexctf.model import Base


def count_of(model: type[Base], *filters: ColumnElement[bool]) -> ScalarSelect[int]:
    """Row count for *model* as a scalar subquery, so counts share one round-trip."""
    return select(func.count()).select_from(model).where(*filters).scalar_subquery()
