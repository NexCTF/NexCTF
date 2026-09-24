"""Unit tests for the plugin registries.

Covers the polymorphic type registry (register/get/compatibility/apply), the
scheduler job registry, the route registry's scope filtering, the frontend
bundle registry, and owner conflicts. Each test uses a fresh registry instance
so it does not touch the module-level singletons the running app populates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import APIRouter
from pydantic import BaseModel

from nexctf.enums import InputType
from nexctf.model import Link
from nexctf.plugins.declare import FrontendDef, JobDef, RouterDef, TypeDef
from nexctf.plugins.frontend import FrontendRegistry
from nexctf.plugins.registry import PolymorphicRegistry, SchedulerRegistry
from nexctf.plugins.routes import RouteRegistry


class _Schema(BaseModel):
    pass


def _register(reg: PolymorphicRegistry, type_name: str, **kwargs) -> None:
    """Register a type on a polymorphic registry with dummy schemas."""
    reg.add(TypeDef(type_name, Link, _Schema, _Schema, _Schema, **kwargs), "tests")


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
    _register(reg, "poly_again", polymorphic=True)
    assert reg.polymorphic_subclasses == [Link]


def test_apply_is_idempotent() -> None:
    """A second apply() is a no-op so test setups can call it repeatedly."""
    reg = PolymorphicRegistry()
    _register(reg, "thing", polymorphic=False)
    reg.register_load_option("extra-option")

    class _Crud:
        model = Link
        default_load_options: list = []

    reg.apply(_Crud)
    reg.apply(_Crud)

    assert _Crud.default_load_options == ["extra-option"]


def test_scheduler_register_and_get() -> None:
    reg = SchedulerRegistry()

    def handler() -> None: ...

    reg.add(JobDef("my_task", handler, _Schema, _Schema), owner="tests")
    entry = reg.get("my_task")
    assert entry.handler is handler
    assert dict(reg.items()) == {"my_task": entry}


def test_scheduler_get_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        SchedulerRegistry().get("nope")


def test_route_registry_keeps_each_scope_of_a_prefix() -> None:
    reg = RouteRegistry()
    admin_router = RouterDef(APIRouter(), prefix="/a", scope="admin")
    user_router = RouterDef(APIRouter(), prefix="/a")
    reg.add(admin_router, owner="demo")
    reg.add(user_router, owner="demo")

    assert reg.get_routers() == [admin_router, user_router]
    assert reg.items() == [("demo", admin_router), ("demo", user_router)]


def test_router_scope_defaults_to_user() -> None:
    assert RouterDef(APIRouter(), prefix="/a").scope == "user"


def test_frontend_is_keyed_on_its_owner() -> None:
    reg = FrontendRegistry()
    reg.add(FrontendDef(Path("/dist")), owner="demo")
    entry = reg.get("demo")
    assert entry is not None
    assert reg.get_all() == [entry]


def test_a_declared_bundle_that_is_not_built_is_reported_missing() -> None:
    reg = FrontendRegistry()
    reg.add(FrontendDef(Path("/dist"), admin_entry_file="admin.js"), owner="demo")
    entry = reg.get("demo")
    assert entry is not None
    assert entry.user is None
    assert entry.admin is None
    assert entry.missing == ["bundle.js", "admin.js"]


def test_each_bundle_carries_its_hashes_and_slots(tmp_path: Path) -> None:
    (tmp_path / "bundle.js").write_text("console.log(1)")
    reg = FrontendRegistry()
    reg.add(FrontendDef(tmp_path, slots=["challenge_panel"]), owner="demo")
    entry = reg.get("demo")
    assert entry is not None and entry.user is not None

    assert entry.user.script.integrity == (
        "sha384-vuz+yO71bcb30P4dMUNzy6/D2y+6d/n0KcOnt5clJtTBxEDoKAqGay0stFlC8Dpr"
    )
    assert entry.user.script.version == "beecfec8eef5"
    assert entry.user.slots == ["challenge_panel"]
    assert entry.bundle(admin=False) is entry.user
    assert entry.missing == []


def test_a_missing_stylesheet_is_reported_but_the_script_still_loads(
    tmp_path: Path,
) -> None:
    (tmp_path / "bundle.js").write_text("console.log(1)")
    reg = FrontendRegistry()
    reg.add(FrontendDef(tmp_path, entry_css="bundle.css"), owner="demo")
    entry = reg.get("demo")
    assert entry is not None and entry.user is not None

    assert entry.user.style is None
    assert entry.user.asset("bundle.js") is entry.user.script
    assert entry.missing == ["bundle.css"]


def test_frontend_get_missing_returns_none() -> None:
    assert FrontendRegistry().get("missing") is None


def _type(name: str) -> TypeDef:
    return TypeDef(name, Link, _Schema, _Schema, _Schema, polymorphic=False)


def test_another_owner_cannot_take_a_type_name() -> None:
    reg = PolymorphicRegistry()
    reg.add(_type("thing"), owner="first")
    with pytest.raises(ValueError, match="already registered by 'first'"):
        reg.add(_type("thing"), owner="second")


def test_the_same_owner_may_register_a_type_again() -> None:
    reg = PolymorphicRegistry()
    reg.add(_type("thing"), owner="first")
    reg.add(_type("thing"), owner="first")
    reg.check("thing", "first")


def test_another_owner_cannot_take_a_job_name() -> None:
    reg = SchedulerRegistry()

    def handler() -> None: ...

    reg.add(JobDef("job", handler, _Schema, _Schema), owner="first")
    with pytest.raises(ValueError, match="already registered by 'first'"):
        reg.add(JobDef("job", handler, _Schema, _Schema), owner="second")
