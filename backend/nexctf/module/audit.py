"""Request-scoped audit context and an ``AsyncCrud`` mixin that auto-logs.

The mixin emits an :class:`~nexctf.model.event.Event` for every create, update
and delete performed through it, capturing a redacted before/after diff. Actor
and IP are read from a context variable populated per request by the admin
router (see ``nexctf.api.dep.set_audit_context``).
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi_toolsets.crud import AsyncCrud
from fastapi_toolsets.schemas import Response
from fastapi_toolsets.types import ModelType
from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.module.events import emit

# Columns whose key contains any of these substrings are never recorded in a
# diff. Substring matching catches plugin-defined variants (e.g. ``flag_hash``,
# ``static_flag``, ``client_secret``). Over-redaction is preferred to leaking.
_SENSITIVE_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "flag",
    "answer",
    "hash",
    "otp",
    "key",
)
# Columns excluded as noise rather than for secrecy.
_SKIP_FIELDS = {"id", "created_at", "updated_at"}
# Attribute names tried, in order, to derive a human-readable target label.
_LABEL_FIELDS = ("title", "name", "label", "username", "slug")
_MAX_VALUE_LEN = 200


@dataclass(frozen=True)
class AuditContext:
    """The actor and origin of the request currently being served."""

    actor_id: UUID | None
    ip: str | None


_audit_ctx: ContextVar[AuditContext | None] = ContextVar("audit_ctx", default=None)


def set_audit_context(ctx: AuditContext) -> None:
    """Bind the audit context for the current request."""
    _audit_ctx.set(ctx)


def current_audit_context() -> AuditContext | None:
    """Return the audit context bound to the current request, if any."""
    return _audit_ctx.get()


REDACTED = "***"


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return key in _SKIP_FIELDS or any(s in lowered for s in _SENSITIVE_SUBSTRINGS)


def _jsonable(value: Any) -> Any:
    """Coerce a column value to something JSON-serialisable and bounded."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = value if isinstance(value, str) else str(value)
    if len(text) > _MAX_VALUE_LEN:
        return text[:_MAX_VALUE_LEN] + "…[truncated]"
    return text


def redact(key: str, value: Any) -> Any:
    """Return a JSON-safe value for ``key``: ``"***"`` when the key is sensitive.

    Shared by the CRUD diff and by callers (e.g. config audit) that build their
    own ``{field: [old, new]}`` meta and must apply the same redaction.
    """
    return REDACTED if _is_sensitive(key) else _jsonable(value)


def _snapshot(instance: object) -> dict[str, Any]:
    """Capture the mapped column values of an instance (no relationships)."""
    mapper = inspect(type(instance))
    return {attr.key: getattr(instance, attr.key) for attr in mapper.column_attrs}


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """Return ``{field: [old, new]}`` for changed, non-sensitive columns."""
    changes: dict[str, list[Any]] = {}
    for key, new in after.items():
        if _is_sensitive(key):
            continue
        old = before.get(key)
        if old != new:
            changes[key] = [_jsonable(old), _jsonable(new)]
    return changes


def _label_for(instance: object) -> str | None:
    for field in _LABEL_FIELDS:
        value = getattr(instance, field, None)
        if isinstance(value, str) and value:
            return value
    return None


def audit_actor() -> tuple[UUID | None, str | None]:
    """Return the (actor_id, ip) bound to the current request, or (None, None)."""
    ctx = current_audit_context()
    return (ctx.actor_id, ctx.ip) if ctx else (None, None)


def _wrap(instance: object, schema: type[BaseModel] | None) -> Any:
    """Mirror AsyncCrud's return shape: ``Response[schema]`` or the raw instance."""
    return Response(data=schema.model_validate(instance)) if schema else instance


async def _emit_write(
    session: AsyncSession,
    table: str,
    action: str,
    *,
    target_id: UUID | None,
    target_label: str | None,
    changes: dict[str, list[Any]] | None = None,
) -> None:
    """Persist an audit event for a create/update/delete on ``table``."""
    actor_id, ip = audit_actor()
    await emit(
        session,
        event_type=f"{table}.{action}",
        actor_id=actor_id,
        target_type=table,
        target_id=target_id,
        target_label=target_label,
        ip=ip,
        meta={"changes": changes} if changes else {},
    )


class AuditedCrud(AsyncCrud[ModelType]):
    """``AsyncCrud`` that records an audit event for each write it performs."""

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        obj: BaseModel,
        *,
        schema: type[BaseModel] | None = None,
    ) -> Any:
        instance = await super().create(session, obj)
        await _emit_write(
            session,
            cls.model.__tablename__,
            "created",
            target_id=getattr(instance, "id", None),
            target_label=_label_for(instance),
            changes=_diff({}, _snapshot(instance)),
        )
        return _wrap(instance, schema)

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
        existing = await super().get_or_none(session, filters)
        before = _snapshot(existing) if existing is not None else {}
        instance = await super().update(
            session,
            obj,
            filters,
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
            with_for_update=with_for_update,
        )
        await _emit_write(
            session,
            cls.model.__tablename__,
            "updated",
            target_id=getattr(instance, "id", None),
            target_label=_label_for(instance),
            changes=_diff(before, _snapshot(instance)),
        )
        return _wrap(instance, schema)

    @classmethod
    async def delete(
        cls,
        session: AsyncSession,
        filters: list[Any],
        *,
        return_response: bool = False,
    ) -> Any:
        # Snapshot identity before deletion: deleted instances get expired.
        targets = [
            (getattr(t, "id", None), _label_for(t))
            for t in await super().get_multi(session, filters=filters)
        ]
        result = await super().delete(session, filters, return_response=return_response)
        table = cls.model.__tablename__
        for target_id, target_label in targets:
            await _emit_write(
                session,
                table,
                "deleted",
                target_id=target_id,
                target_label=target_label,
            )
        return result
