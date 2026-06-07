"""Unit tests for the plugin registries.

Covers the polymorphic type registry (register/get/compatibility/apply), the
scheduler job registry, the route registry's scope filtering, and the frontend
bundle registry. Each test uses a fresh registry instance so it does not touch
the module-level singletons the running app populates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import APIRouter
from pydantic import BaseModel

from nexctf.enums import InputType
from nexctf.model import Tag
from nexctf.plugins.frontend import FrontendRegistry
from nexctf.plugins.registry import PolymorphicRegistry, SchedulerRegistry
from nexctf.plugins.routes import RouteRegistry


class _Schema(BaseModel):
    pass


def _register(reg: PolymorphicRegistry, type_name: str, **kwargs) -> None:
    """Register a type on a polymorphic registry with dummy schemas."""
    reg.register(
        type_name,
        Tag,
        create_schema=_Schema,
        update_schema=_Schema,
        read_schema=_Schema,
        **kwargs,
    )


def test_register_then_get_returns_entry() -> None:
    reg = PolymorphicRegistry()
    _register(reg, "thing", description="A thing")
    entry = reg.get("thing")
    assert entry.create_schema is _Schema
    assert entry.description == "A thing"


def test_get_unknown_type_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        PolymorphicRegistry().get("missing")


def test_compatible_with_filters_by_input_type() -> None:
    """``None`` compatibility means "all input types"; a list restricts it."""
    reg = PolymorphicRegistry()
    _register(reg, "input_only", compatible_input_types=[InputType.INPUT])
    _register(reg, "any", compatible_input_types=None)
    _register(reg, "mcq_only", compatible_input_types=[InputType.MCQ])

    assert set(reg.compatible_with(InputType.INPUT)) == {"input_only", "any"}
    assert set(reg.compatible_with(InputType.MCQ)) == {"mcq_only", "any"}


def test_polymorphic_flag_controls_subclass_registration() -> None:
    reg = PolymorphicRegistry()
    _register(reg, "poly", polymorphic=True)
    _register(reg, "flat", polymorphic=False)
    assert reg.polymorphic_subclasses == [Tag]


def test_apply_is_idempotent() -> None:
    """A second apply() is a no-op so test setups can call it repeatedly."""
    reg = PolymorphicRegistry()
    _register(reg, "thing", polymorphic=False)
    reg.register_load_option("extra-option")

    class _Crud:
        model = Tag
        default_load_options: list = []

    reg.apply(_Crud)
    reg.apply(_Crud)

    assert _Crud.default_load_options == ["extra-option"]


def test_scheduler_register_and_get() -> None:
    reg = SchedulerRegistry()

    def handler() -> None: ...

    reg.register(
        "my_task", handler=handler, create_schema=_Schema, update_schema=_Schema
    )
    entry = reg.get("my_task")
    assert entry.handler is handler
    assert dict(reg.items()) == {"my_task": entry}


def test_scheduler_get_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        SchedulerRegistry().get("nope")


def test_route_registry_filters_by_scope() -> None:
    reg = RouteRegistry()
    admin_router = APIRouter()
    public_router = APIRouter()
    reg.register(admin_router, prefix="/a", scope="admin")
    reg.register(public_router, prefix="/p", scope="public")

    admin = reg.get_routers(scope="admin")
    public = reg.get_routers(scope="public")
    assert [r for r, _, _ in admin] == [admin_router]
    assert [r for r, _, _ in public] == [public_router]


def test_route_registry_returns_all_without_scope() -> None:
    reg = RouteRegistry()
    reg.register(APIRouter(), prefix="/a", scope="admin")
    reg.register(APIRouter(), prefix="/p", scope="public")
    assert len(reg.get_routers()) == 2


def test_route_registry_defaults_tags_to_empty_list() -> None:
    reg = RouteRegistry()
    reg.register(APIRouter(), prefix="/a")
    ((_, prefix, tags),) = reg.get_routers()
    assert prefix == "/a"
    assert tags == []


def test_frontend_register_get_and_get_all() -> None:
    reg = FrontendRegistry()
    reg.register(key="fe", dist_dir=Path("/dist"), slots=["challenge_panel"])
    entry = reg.get("fe")
    assert entry is not None
    assert entry.slots == ["challenge_panel"]
    assert entry.entry_file == "bundle.js"
    assert reg.get_all() == [entry]


def test_frontend_get_missing_returns_none() -> None:
    assert FrontendRegistry().get("missing") is None
