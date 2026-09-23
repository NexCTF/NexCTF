"""Registries plugins register their polymorphic types and scheduler jobs with."""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi_toolsets.crud import CrudFactory
from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.orm import selectinload

from nexctf.enums import InputType
from nexctf.plugins.declare import JobDef, SchemaClass, TypeDef

if TYPE_CHECKING:
    from redis.asyncio import Redis


class _OwnedNames:
    """Tracks which plugin owns each registered name."""

    _kind: str

    def __init__(self) -> None:
        self._owners: dict[str, str] = {}

    def check(self, name: str, owner: str) -> None:
        """Raise unless ``owner`` may register ``name``: it is free or already theirs.

        Raises:
            ValueError: If another owner already registered ``name``.
        """
        current = self._owners.get(name, owner)
        if current != owner:
            raise ValueError(
                f"{self._kind} {name!r} is already registered by {current!r}"
            )

    def _claim(self, name: str, owner: str) -> None:
        """Record ``owner`` as the owner of ``name`` after checking it may take it."""
        self.check(name, owner)
        self._owners[name] = owner


@dataclasses.dataclass
class RegistryEntry:
    """A registered polymorphic type's CRUD factory and Pydantic schemas."""

    crud: Any
    create_schema: SchemaClass
    update_schema: SchemaClass
    read_schema: SchemaClass
    compatible_input_types: list[InputType] | None = None
    description: str | None = None


def _auto_load_options(model: Any) -> list[Any]:
    """Build selectinload options for every relationship on a model.

    Args:
        model: The SQLAlchemy model to inspect.

    Returns:
        A selectinload option for each of the model's relationships.
    """
    mapper = inspect(model)
    return [selectinload(getattr(model, rel.key)) for rel in mapper.relationships]


class PolymorphicRegistry(_OwnedNames):
    """Maps a polymorphic type name to its CrudFactory and Pydantic schemas."""

    _kind = "type"

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[str, RegistryEntry] = {}
        self._extra_load_options: list[Any] = []
        self._polymorphic_subclasses: dict[Any, None] = {}
        self._applied: bool = False

    def add(self, type_def: TypeDef, owner: str) -> None:
        """Register a type on behalf of ``owner``; its re-registration replaces it.

        Raises:
            ValueError: If another owner already registered the type name.
        """
        self._claim(type_def.name, owner)
        crud = CrudFactory(
            model=type_def.model,
            default_load_options=_auto_load_options(type_def.model),
            m2m_fields=type_def.m2m_fields or None,
        )
        self._entries[type_def.name] = RegistryEntry(
            crud=crud,
            create_schema=type_def.create_schema,
            update_schema=type_def.update_schema,
            read_schema=type_def.read_schema,
            compatible_input_types=type_def.compatible_input_types,
            description=type_def.description,
        )
        if type_def.polymorphic:
            self._polymorphic_subclasses[type_def.model] = None

    def register_load_option(self, option: Any) -> None:
        """Register an extra SQLAlchemy load option for the base CRUD query.

        Args:
            option: A SQLAlchemy load option (e.g. ``selectinload(...)``).
        """
        self._extra_load_options.append(option)

    def apply(self, crud_class: Any) -> None:
        """Patch a base CRUD class with all registered load options.

        Args:
            crud_class: The base CRUD class to patch in place.
        """
        if self._applied:
            return
        self._applied = True
        extra = list(self._extra_load_options)
        if self._polymorphic_subclasses:
            from sqlalchemy.orm import selectin_polymorphic

            extra.insert(
                0,
                selectin_polymorphic(
                    crud_class.model, list(self._polymorphic_subclasses)
                ),
            )
        if extra:
            crud_class.default_load_options = [
                *(crud_class.default_load_options or []),
                *extra,
            ]

    def get(self, type_name: str) -> RegistryEntry:
        """Return the entry registered under a type name.

        Args:
            type_name: The polymorphic type name to look up.

        Returns:
            The registered entry.

        Raises:
            KeyError: If no entry is registered under ``type_name``.
        """
        if type_name not in self._entries:
            raise KeyError(type_name)
        return self._entries[type_name]

    def compatible_with(self, input_type: InputType) -> dict[str, RegistryEntry]:
        """Return the entries compatible with an input type.

        Args:
            input_type: The input type to filter by.

        Returns:
            A mapping of type name to entry for the compatible types.
        """
        return {
            name: entry
            for name, entry in self._entries.items()
            if entry.compatible_input_types is None
            or input_type in entry.compatible_input_types
        }

    @property
    def polymorphic_subclasses(self) -> list[Any]:
        """The models registered as polymorphic subclasses."""
        return list(self._polymorphic_subclasses)

    def items(self):
        """Return an items view of ``(type_name, entry)`` pairs."""
        return self._entries.items()


challenge_registry = PolymorphicRegistry()
solution_registry = PolymorphicRegistry()


@dataclasses.dataclass
class SchedulerEntry:
    """A registered job type, its handler/schemas and post-run cache drop."""

    type_name: str
    handler: Callable  # sync or async: handler(job, session, redis)
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    invalidate: Callable[[Redis], Awaitable[None]] | None = None


class SchedulerRegistry(_OwnedNames):
    """Maps job type names to their handlers and Pydantic schemas."""

    _kind = "job"

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[str, SchedulerEntry] = {}

    def add(self, job: JobDef, owner: str) -> None:
        """Register a job type on behalf of ``owner``.

        Raises:
            ValueError: If another owner already registered the job type.
        """
        self._claim(job.type_name, owner)
        self._entries[job.type_name] = SchedulerEntry(
            type_name=job.type_name,
            handler=job.handler,
            create_schema=job.create_schema,
            update_schema=job.update_schema,
            invalidate=job.invalidate,
        )

    def get(self, type_name: str) -> SchedulerEntry:
        """Return the entry registered under a job type name.

        Args:
            type_name: The job type name to look up.

        Returns:
            The registered entry.

        Raises:
            KeyError: If no entry is registered under ``type_name``.
        """
        return self._entries[type_name]

    def items(self):
        """Return an items view of ``(type_name, entry)`` pairs."""
        return self._entries.items()


scheduler_registry = SchedulerRegistry()
