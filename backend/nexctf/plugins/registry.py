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

if TYPE_CHECKING:
    from redis.asyncio import Redis

type SchemaClass = type[BaseModel]


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


class PolymorphicRegistry:
    """Maps a polymorphic type name to its CrudFactory and Pydantic schemas."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        self._extra_load_options: list[Any] = []
        self._polymorphic_subclasses: list[Any] = []
        self._applied: bool = False

    def register(
        self,
        type_name: str,
        model: Any,
        create_schema: SchemaClass,
        update_schema: SchemaClass,
        read_schema: SchemaClass,
        m2m_fields: dict[str, Any] | None = None,
        compatible_input_types: list[InputType] | None = None,
        description: str | None = None,
        polymorphic: bool = True,
    ) -> None:
        """Register a polymorphic type with its CRUD factory and schemas.

        Args:
            type_name: The polymorphic type name to register under.
            model: The SQLAlchemy model for this type.
            create_schema: Schema used to create instances.
            update_schema: Schema used to update instances.
            read_schema: Schema used to serialise instances.
            m2m_fields: Many-to-many fields exposed on create/update.
            compatible_input_types: Input types this type accepts, or ``None`` for all.
            description: Human-readable description shown in the admin UI.
            polymorphic: Whether to register the model as a polymorphic subclass.
        """
        crud = CrudFactory(
            model=model,
            default_load_options=_auto_load_options(model),
            m2m_fields=m2m_fields or None,
        )
        self._entries[type_name] = RegistryEntry(
            crud=crud,
            create_schema=create_schema,
            update_schema=update_schema,
            read_schema=read_schema,
            compatible_input_types=compatible_input_types,
            description=description,
        )
        if polymorphic:
            self._polymorphic_subclasses.append(model)

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
                selectin_polymorphic(crud_class.model, self._polymorphic_subclasses),
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


class SchedulerRegistry:
    """Maps job type names to their handlers and Pydantic schemas.

    Plugin authors call :meth:`register` from their plugin's ``__init__.py``::

        scheduler_registry.register(
            type_name="my_task",
            handler=my_handler,
            create_schema=MyTaskParams,
            update_schema=MyTaskParams,
        )
    """

    def __init__(self) -> None:
        self._entries: dict[str, SchedulerEntry] = {}

    def register(
        self,
        type_name: str,
        handler: Callable,
        create_schema: type[BaseModel],
        update_schema: type[BaseModel],
        invalidate: Callable[[Redis], Awaitable[None]] | None = None,
    ) -> None:
        """Register a job type with its handler and schemas.

        Args:
            type_name: The job type name to register under.
            handler: The sync or async callable that runs the job.
            create_schema: Schema used to create jobs of this type.
            update_schema: Schema used to update jobs of this type.
            invalidate: Cache drop run after the run commits, when the handler
                changes state that is cached elsewhere.
        """
        self._entries[type_name] = SchedulerEntry(
            type_name=type_name,
            handler=handler,
            create_schema=create_schema,
            update_schema=update_schema,
            invalidate=invalidate,
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
