"""Declarative plugin description, committed by the loader in one step."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from fastapi import APIRouter
    from redis.asyncio import Redis

    from nexctf.core.appconfig import ConfigDef
    from nexctf.enums import InputType

type SchemaClass = type[BaseModel]
type RouterScope = Literal["admin", "user", "anonymous"]


@dataclass(frozen=True)
class TypeDef:
    """A polymorphic challenge or solution type."""

    name: str
    model: Any
    create_schema: SchemaClass
    update_schema: SchemaClass
    read_schema: SchemaClass
    m2m_fields: dict[str, Any] | None = None
    compatible_input_types: list[InputType] | None = None
    description: str | None = None
    polymorphic: bool = True


@dataclass(frozen=True)
class JobDef:
    """A scheduler job type; ``handler(job, session, redis)`` may be sync or async."""

    type_name: str
    handler: Callable
    create_schema: SchemaClass
    update_schema: SchemaClass
    invalidate: Callable[[Redis], Awaitable[None]] | None = None


@dataclass(frozen=True)
class RouterDef:
    """An API router mounted under ``prefix``.

    ``admin`` mounts under ``/admin`` behind admin auth, ``user`` requires a
    signed-in user, ``anonymous`` adds no authentication.
    """

    router: APIRouter
    prefix: str
    scope: RouterScope = "user"
    tags: list[str | Enum] = field(default_factory=list)


@dataclass(frozen=True)
class FrontendDef:
    """A prebuilt frontend bundle and the UI slots it fills."""

    dist_dir: Path
    slots: list[str]
    challenge_types: list[str] | None = None
    entry_file: str = "bundle.js"


@dataclass(eq=False)
class ConfigCategory:
    """Config keys shown under one settings category, prefixed with the plugin key."""

    display_name: str
    defs: tuple[ConfigDef, ...]
    icon: str | None = None
    section: str = "plugins"
    key: str | None = field(default=None, init=False)

    def get(self, name: str, overrides: dict[str, str]) -> str | int | float | bool:
        """Resolve one of these keys once the loader has bound the category.

        Args:
            name: Bare config key, e.g. ``"instance_url"``.
            overrides: Config snapshot from ``appconfig.fetch_overrides``.

        Raises:
            LookupError: If no loaded plugin declared this category.
        """
        if self.key is None:
            raise LookupError(
                f"config {self.display_name!r} belongs to no loaded plugin"
            )
        from nexctf.core.appconfig import get_with_overrides

        return get_with_overrides(f"{self.key}.{name}", overrides)


@dataclass
class Plugin:
    """Everything a plugin contributes, registered only once all of it validates.

    Atomicity covers NexCTF registrations: a failed plugin registers no type,
    route, job, config or bundle. Import side effects, such as models already
    mapped on the declarative base, are not undone.
    """

    challenge_types: list[TypeDef] = field(default_factory=list)
    solution_types: list[TypeDef] = field(default_factory=list)
    jobs: list[JobDef] = field(default_factory=list)
    routers: list[RouterDef] = field(default_factory=list)
    config: ConfigCategory | None = None
    frontend: FrontendDef | None = None
