"""Unit tests for nexctf.plugins.loader."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
import textwrap
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from nexctf.api import scope
from nexctf.core import appconfig
from nexctf.plugins import ConfigCategory, loader, registry, routes

_EMPTY_PLUGIN = "from nexctf.plugins import Plugin\nplugin = Plugin()\nvalue = 1\n"


@pytest.fixture(autouse=True)
def _isolate_loader_state(
    isolated_plugins: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Give each test fresh loader registries so fake plugins cannot leak out."""
    monkeypatch.setattr(loader, "_plugin_metadata", {})
    monkeypatch.setattr(loader, "_plugin_tables", set())
    monkeypatch.setattr(loader, "_plugin_migrations", {})


@pytest.fixture
def plugins_root(tmp_path: Path) -> Iterator[Path]:
    """A temp directory on sys.path holding importable fake plugin packages."""
    root = tmp_path / "root"
    root.mkdir()
    sys.path.insert(0, str(root))
    yield root
    sys.path.remove(str(root))
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if file and str(root) in file:
            del sys.modules[name]


def _write_package(root: Path, name: str, body: str = _EMPTY_PLUGIN) -> Path:
    """Write an importable package into the plugins root."""
    package = root / name
    package.mkdir()
    package.joinpath("__init__.py").write_text(body)
    return package


class _FakeDistribution(importlib.metadata.Distribution):
    """A distribution whose metadata comes from a literal header block."""

    def __init__(self, headers: str) -> None:
        self._headers = textwrap.dedent(headers)

    def read_text(self, filename: str) -> str | None:
        return self._headers if filename == "METADATA" else None

    def locate_file(self, path):  # pragma: no cover - unused
        return Path(path)


@dataclass
class _FakeEntryPoint:
    """The slice of an entry point the loader reads: its target and its dist."""

    module: str
    dist: importlib.metadata.Distribution | None
    attr: str | None = None


def _fake_entry_point(
    module: str, headers: str, attr: str | None = None
) -> _FakeEntryPoint:
    """Build an entry point bound to a fake distribution."""
    return _FakeEntryPoint(module, _FakeDistribution(headers), attr)


def _install(monkeypatch: pytest.MonkeyPatch, *entry_points) -> None:
    """Make ``entry_points(group=...)`` return the given fakes."""
    monkeypatch.setattr(
        loader.importlib.metadata, "entry_points", lambda group: list(entry_points)
    )


def test_plugin_key_normalises_distribution_names() -> None:
    """Distribution names normalise per PEP 503 so one plugin has one key."""
    assert loader.plugin_key("NexCTF-Sandbox") == "nexctf_sandbox"
    assert loader.plugin_key("nexctf.sandbox") == "nexctf_sandbox"


def test_display_name_strips_the_plugin_prefix() -> None:
    assert loader._display_name("nexctf-sandbox") == "Sandbox"
    assert loader._display_name("nexctf-plugin-container") == "Container"
    assert loader._display_name("my-thing") == "My Thing"


def test_installed_metadata_reads_distribution_headers() -> None:
    dist = _FakeDistribution("""\
        Metadata-Version: 2.1
        Name: nexctf-demo
        Version: 1.2.3
        Summary: A demo plugin
        Author-email: Alice <alice@example.com>
        Project-URL: Repository, https://example.com/repo
        Project-URL: Homepage, https://example.com
        """)
    meta = loader._installed_metadata("nexctf_demo", dist)
    assert meta.name == "nexctf-demo"
    assert meta.display_name == "Demo"
    assert meta.version == "1.2.3"
    assert meta.description == "A demo plugin"
    assert meta.authors == ["Alice"]
    assert meta.repo_url == "https://example.com/repo"
    assert meta.homepage_url == "https://example.com"
    assert meta.is_builtin is False
    assert meta.is_active is True
    assert meta.load_error is None


def test_load_imports_entry_point_and_keys_on_distribution_name(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_package(plugins_root, "good_pkg")
    _install(
        monkeypatch,
        _fake_entry_point("good_pkg", "Name: nexctf-good\nVersion: 1.0.0\n"),
    )

    loader._load_installed_plugins()

    meta = loader._plugin_metadata["nexctf_good"]
    assert meta.name == "nexctf-good"
    assert meta.is_active is True
    assert sys.modules["good_pkg"].value == 1


def test_two_plugins_get_separate_keys(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each distribution loads under its own key, so wheels cannot overwrite
    each other's metadata or share an Alembic version table."""
    _write_package(plugins_root, "one_pkg")
    _write_package(plugins_root, "two_pkg")
    _install(
        monkeypatch,
        _fake_entry_point("one_pkg", "Name: nexctf-one\nVersion: 1.0\n"),
        _fake_entry_point("two_pkg", "Name: nexctf-two\nVersion: 2.0\n"),
    )

    loader._load_installed_plugins()

    assert set(loader._plugin_metadata) == {"nexctf_one", "nexctf_two"}
    assert {"one_pkg", "two_pkg"} <= set(sys.modules)


def test_installed_plugin_failure_is_captured_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plugin that fails to import is recorded, not fatal.

    This is the resilience guarantee for user-installed plugins: one broken
    plugin must not take down startup, and the admin UI needs the error.
    """
    _install(
        monkeypatch,
        _fake_entry_point("missing_pkg", "Name: nexctf-bad\nVersion: 1.0\n"),
    )

    loader._load_installed_plugins()

    meta = loader._plugin_metadata["nexctf_bad"]
    assert meta.is_active is False
    assert meta.load_error  # carries the import error text


def test_already_loaded_plugin_is_not_reimported(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key already loaded is skipped (first loader wins)."""
    sentinel = loader._builtin_metadata("nexctf_dup")
    loader._plugin_metadata["nexctf_dup"] = sentinel
    _write_package(plugins_root, "dup_pkg")
    _install(
        monkeypatch,
        _fake_entry_point("dup_pkg", "Name: nexctf-dup\nVersion: 1.0\n"),
    )

    loader._load_installed_plugins()

    assert loader._plugin_metadata["nexctf_dup"] is sentinel
    assert "dup_pkg" not in sys.modules


@pytest.mark.parametrize(
    ("include_disabled", "imported"), [(False, False), (True, True)]
)
def test_a_disabled_plugin_is_skipped_except_for_migrations(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    include_disabled: bool,
    imported: bool,
) -> None:
    """Disabled by distribution name, so the operator writes what they installed."""
    _write_package(plugins_root, "off_pkg")
    _install(
        monkeypatch, _fake_entry_point("off_pkg", "Name: nexctf-off\nVersion: 1\n")
    )
    monkeypatch.setenv("NEXCTF_DISABLED_PLUGINS", "other, nexctf-off")

    loader._load_installed_plugins(include_disabled=include_disabled)

    meta = loader._plugin_metadata["nexctf_off"]
    assert (meta.is_active, meta.is_disabled) == (imported, not imported)
    assert meta.load_error is None
    assert ("off_pkg" in sys.modules) is imported


def test_no_installed_plugins_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    loader._load_installed_plugins()
    assert loader._plugin_metadata == {}


def test_derive_owned_tables_from_package() -> None:
    """Owned tables derive from the models' __tablename__, so plugin authors
    declare each table once (on the model) and never restate it elsewhere."""
    tables = loader.derive_owned_tables("nexctf.plugins.builtin.solution")
    assert {"solutions_mcq", "solutions_regex", "solutions_match"} <= tables


def test_derive_owned_tables_empty_for_unknown_package() -> None:
    """A plugin with no models of its own owns no tables to exclude."""
    assert loader.derive_owned_tables("nexctf_nothing_here") == frozenset()


def test_migrations_are_recorded_only_for_plugins_that_ship_them(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migrations are captured while loading, so builtins — whose tables live in
    the core schema and core history — can never reach the plugin migrator."""
    _write_package(plugins_root, "plain_pkg")
    migrated = _write_package(plugins_root, "migrated_pkg")
    (migrated / "alembic" / "versions").mkdir(parents=True)
    _install(
        monkeypatch,
        _fake_entry_point("plain_pkg", "Name: nexctf-plain\nVersion: 1.0\n"),
        _fake_entry_point("migrated_pkg", "Name: nexctf-migrated\nVersion: 1.0\n"),
    )

    loader.load_builtin_plugins()
    loader._load_installed_plugins()
    found = loader.get_plugin_migrations()

    assert set(found) == {"nexctf_migrated"}
    versions, owned = found["nexctf_migrated"]
    assert versions.is_dir()
    assert owned == frozenset()


def test_load_builtin_plugins_registers_real_types() -> None:
    """Loading the in-tree builtin plugins registers their challenge/solution types."""
    from nexctf.plugins import challenge_registry, solution_registry

    loader.load_builtin_plugins()

    challenge_types = {name for name, _ in challenge_registry.items()}
    solution_types = {name for name, _ in solution_registry.items()}
    assert "standard" in challenge_types
    assert {"mcq", "regex", "match"} <= solution_types
    assert {"challenge", "solution"} <= set(loader._plugin_metadata)
    assert loader._plugin_metadata["solution"].is_builtin is True


def _load_one(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    *,
    package: str = "demo_pkg",
    attr: str | None = None,
) -> loader.PluginMeta:
    """Load a single fake plugin distribution ``nexctf-demo`` and return its metadata."""
    _write_package(plugins_root, package, textwrap.dedent(body))
    _install(
        monkeypatch,
        _fake_entry_point(package, "Name: nexctf-demo\nVersion: 1.0\n", attr),
    )
    loader._load_installed_plugins()
    return loader._plugin_metadata["nexctf_demo"]


_DECLARED = """\
    from fastapi import APIRouter
    from pydantic import BaseModel

    from nexctf.model import Link
    from nexctf.plugins import (
        ConfigCategory, ConfigDef, ConfigType, JobDef, Plugin, RouterDef, TypeDef,
    )

    class Schema(BaseModel):
        pass

    def handler(job, session, redis): ...

    plugin = Plugin(
        solution_types=[TypeDef("demo_type", Link, Schema, Schema, Schema, polymorphic=False)],
        jobs=[JobDef("demo_job", handler, Schema, Schema)],
        routers=[RouterDef(APIRouter(), "/demo"), RouterDef(APIRouter(), "/demo", scope="admin")],
        config=ConfigCategory("Demo", (ConfigDef(key="url", label="URL", default="https://a.test", type=ConfigType.URL),)),
    )
    """


def test_a_declared_plugin_registers_everything_under_its_key(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = _load_one(plugins_root, monkeypatch, _DECLARED)

    assert meta.is_active, meta.load_error
    with pytest.raises(ValueError, match="by 'nexctf_demo'"):
        registry.solution_registry.check("demo_type", "other")
    with pytest.raises(ValueError, match="by 'nexctf_demo'"):
        registry.scheduler_registry.check("demo_job", "other")
    assert len(routes.route_registry.get_routers()) == 2
    assert scope.group_for_path("/api/v1/demo/x") == "plugin.nexctf_demo"
    assert scope.group_for_path("/api/v1/admin/demo/x") == "admin.plugin.nexctf_demo"
    assert appconfig.get_def("nexctf_demo.url").category == "nexctf_demo"


def test_the_entry_point_attribute_names_the_plugin(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = _DECLARED.replace("    plugin = Plugin(", "    custom = Plugin(")
    meta = _load_one(plugins_root, monkeypatch, body, attr="custom")
    assert meta.is_active, meta.load_error


def test_an_entry_point_without_a_plugin_fails(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = _load_one(plugins_root, monkeypatch, "value = 1\n")
    assert meta.is_active is False
    assert "is not a nexctf.plugins.Plugin" in (meta.load_error or "")


def test_a_pre_plugin_style_plugin_fails_and_registers_nothing(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registries have no ``register`` any more, so an old plugin fails on import."""
    body = """\
        from pydantic import BaseModel

        from nexctf.model import Link
        from nexctf.plugins import solution_registry

        class Schema(BaseModel):
            pass

        solution_registry.register("legacy_type", Link, Schema, Schema, Schema)
        """
    meta = _load_one(plugins_root, monkeypatch, body)

    assert meta.is_active is False
    assert "has no attribute 'register'" in (meta.load_error or "")
    with pytest.raises(KeyError):
        registry.solution_registry.get("legacy_type")


def test_a_plugin_failing_validation_registers_nothing(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One bad part (here a router) keeps every other part out too."""
    body = _DECLARED.replace(
        'RouterDef(APIRouter(), "/demo"),', 'RouterDef(APIRouter(), "/challenges"),'
    )
    meta = _load_one(plugins_root, monkeypatch, body)

    assert meta.is_active is False
    assert "collides with '/challenges'" in (meta.load_error or "")
    with pytest.raises(KeyError):
        registry.solution_registry.get("demo_type")
    with pytest.raises(KeyError):
        registry.scheduler_registry.get("demo_job")
    assert routes.route_registry.get_routers() == []
    assert scope.group_for_path("/api/v1/admin/demo/x") is None
    with pytest.raises(KeyError):
        appconfig.get_def("nexctf_demo.url")


def test_an_invalid_config_def_registers_nothing(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Config is checked with the rest, not discovered broken halfway through."""
    body = _DECLARED.replace(", type=ConfigType.URL)", ")")
    meta = _load_one(plugins_root, monkeypatch, body)

    assert meta.is_active is False
    assert "type= is required" in (meta.load_error or "")
    with pytest.raises(KeyError):
        registry.solution_registry.get("demo_type")
    assert routes.route_registry.get_routers() == []


def test_a_plugin_cannot_take_a_builtin_type(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader.load_builtin_plugins()
    body = _DECLARED.replace('TypeDef("demo_type"', 'TypeDef("match"')
    meta = _load_one(plugins_root, monkeypatch, body)

    assert meta.is_active is False
    assert "'match' is already registered by 'solution'" in (meta.load_error or "")


@pytest.mark.parametrize(
    ("router", "error"),
    [
        ('RouterDef(APIRouter(), "/admin/x")', "collides with '/admin'"),
        ('RouterDef(APIRouter(), "/auth")', "collides with '/auth'"),
        ('RouterDef(APIRouter(), "demo")', "is not like '/name'"),
        ('RouterDef(APIRouter(), "/x", scope="public")', "has scope 'public'"),
    ],
)
def test_a_bad_router_fails_the_plugin(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch, router: str, error: str
) -> None:
    body = _DECLARED.replace('RouterDef(APIRouter(), "/demo"),', f"{router},")
    meta = _load_one(plugins_root, monkeypatch, body)

    assert meta.is_active is False
    assert error in (meta.load_error or "")


def test_the_config_category_is_bound_to_the_plugin_key(
    plugins_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plugin code reads its settings through the category it declared."""
    _load_one(plugins_root, monkeypatch, _DECLARED)
    category = importlib.import_module("demo_pkg").plugin.config

    assert category.key == "nexctf_demo"
    assert category.get("url", {}) == "https://a.test"
    assert category.get("url", {"nexctf_demo.url": "https://b.test"}) == (
        "https://b.test"
    )


def test_an_unbound_config_category_raises() -> None:
    category = ConfigCategory("Demo", ())
    with pytest.raises(LookupError):
        category.get("url", {})


def test_a_plain_secret_is_warned_about(
    plugins_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = _DECLARED.replace('ConfigDef(key="url"', 'ConfigDef(key="api_token"')
    _load_one(plugins_root, monkeypatch, body)
    assert "plugin.config.plain_secret key=nexctf_demo.api_token" in caplog.text
