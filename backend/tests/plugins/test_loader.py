"""Unit tests for nexctf.plugins.loader.

These cover pyproject parsing, metadata building, and the directory scanner,
including the two behaviours that distinguish builtin from store plugins:
a store plugin that fails to load is recorded (not fatal), while a builtin
failure must propagate because it is an in-tree code bug.
"""

from __future__ import annotations

import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from nexctf.plugins import loader


@pytest.fixture(autouse=True)
def _isolate_loader_state() -> Iterator[None]:
    """Reset the loader's module-global registries around each test.

    The loader records imported modules, metadata, and table names in
    module-level containers; isolating them keeps tests independent and stops
    fake plugins from leaking into other tests.
    """
    saved_loaded = dict(loader._loaded)
    saved_meta = dict(loader._plugin_metadata)
    saved_tables = set(loader._plugin_tables)
    loader._loaded.clear()
    loader._plugin_metadata.clear()
    loader._plugin_tables.clear()
    yield
    loader._loaded.clear()
    loader._loaded.update(saved_loaded)
    loader._plugin_metadata.clear()
    loader._plugin_metadata.update(saved_meta)
    loader._plugin_tables.clear()
    loader._plugin_tables.update(saved_tables)


@pytest.fixture
def plugins_root(tmp_path: Path) -> Iterator[Path]:
    """A temp directory on sys.path that holds fake plugins and modules.

    Entry-point modules are written here as top-level modules so that the
    loader's ``importlib.import_module`` can resolve them. sys.path and any
    modules imported from the directory are cleaned up afterwards.
    """
    root = tmp_path / "root"
    root.mkdir()
    sys.path.insert(0, str(root))
    yield root
    sys.path.remove(str(root))
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if file and str(root) in file:
            del sys.modules[name]


def _write_module(root: Path, module_name: str, body: str = "value = 1") -> None:
    """Write an importable top-level module into the plugins root."""
    (root / f"{module_name}.py").write_text(body)


def _write_plugin(
    root: Path,
    dir_name: str,
    *,
    name: str,
    entry_points: dict[str, str],
    version: str = "1.0.0",
) -> Path:
    """Write a fake plugin directory with a minimal pyproject.toml."""
    plugin_dir = root / dir_name
    plugin_dir.mkdir()
    ep_lines = "\n".join(f'{key} = "{path}"' for key, path in entry_points.items())
    plugin_dir.joinpath("pyproject.toml").write_text(
        textwrap.dedent(f"""\
            [project]
            name = "{name}"
            version = "{version}"

            [project.entry-points."nexctf.plugins"]
            {ep_lines}
            """)
    )
    return plugin_dir


def test_read_pyproject_parses_toml(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "demo"\nversion = "2.0"\n')
    data = loader.read_pyproject(path)
    assert data["project"]["name"] == "demo"
    assert data["project"]["version"] == "2.0"


def test_get_entry_points_returns_nexctf_plugins() -> None:
    data = {"project": {"entry-points": {"nexctf.plugins": {"a": "mod.a"}}}}
    assert loader.get_entry_points(data) == {"a": "mod.a"}


def test_get_entry_points_missing_is_empty() -> None:
    """A pyproject without the entry-point table yields no entry points."""
    assert loader.get_entry_points({"project": {}}) == {}


def test_parse_metadata_full() -> None:
    data = {
        "project": {
            "name": "nexctf_demo",
            "version": "1.2.3",
            "description": "A demo plugin",
            "authors": [{"name": "Alice"}, {"name": "Bob"}],
            "urls": {"Repository": "https://example.com/repo", "Homepage": "https://h"},
        },
        "tool": {"nexctf": {"display_name": "Demo"}},
    }
    meta = loader.parse_plugin_metadata("demo", data, is_builtin=True)
    assert meta.key == "demo"
    assert meta.name == "nexctf_demo"
    assert meta.display_name == "Demo"
    assert meta.version == "1.2.3"
    assert meta.authors == ["Alice", "Bob"]
    assert meta.repo_url == "https://example.com/repo"
    assert meta.homepage_url == "https://h"
    assert meta.is_builtin is True
    assert meta.is_active is True
    assert meta.load_error is None


def test_parse_metadata_name_and_display_fall_back_to_key() -> None:
    """With no project name, the key is used for both name and display name."""
    meta = loader.parse_plugin_metadata("fallback", {}, is_builtin=False)
    assert meta.name == "fallback"
    assert meta.display_name == "fallback"


def test_parse_metadata_filters_authors_without_name() -> None:
    """Authors must be dicts carrying a non-empty name; others are dropped."""
    data = {"project": {"authors": [{"name": "Real"}, {"email": "x@y"}, "nope"]}}
    meta = loader.parse_plugin_metadata("k", data, is_builtin=True)
    assert meta.authors == ["Real"]


def test_parse_metadata_urls_are_case_insensitive() -> None:
    data = {"project": {"urls": {"repository": "https://r", "homepage": "https://h"}}}
    meta = loader.parse_plugin_metadata("k", data, is_builtin=True)
    assert meta.repo_url == "https://r"
    assert meta.homepage_url == "https://h"


def test_parse_metadata_records_failure_state() -> None:
    meta = loader.parse_plugin_metadata(
        "k", {}, is_builtin=False, is_active=False, load_error="boom"
    )
    assert meta.is_active is False
    assert meta.load_error == "boom"


def test_load_imports_entry_points_and_records_metadata(plugins_root: Path) -> None:
    _write_module(plugins_root, "good_mod")
    _write_plugin(
        plugins_root, "good", name="nexctf_good", entry_points={"good": "good_mod"}
    )

    loader._load_plugins_from_dir(plugins_root, is_builtin=True)

    assert "good" in loader._loaded
    meta = loader._plugin_metadata["good"]
    assert meta.name == "nexctf_good"
    assert meta.is_active is True
    assert meta.load_error is None


def test_store_plugin_failure_is_captured_not_raised(plugins_root: Path) -> None:
    """A store plugin that fails to import is recorded, not fatal.

    This is the resilience guarantee for user-provided plugins: one broken
    plugin must not take down startup, and the admin UI needs the error.
    """
    _write_plugin(
        plugins_root, "bad", name="nexctf_bad", entry_points={"bad": "missing_mod"}
    )

    loader._load_plugins_from_dir(plugins_root, is_builtin=False)

    assert "bad" not in loader._loaded
    meta = loader._plugin_metadata["bad"]
    assert meta.is_active is False
    assert meta.load_error  # carries the import error text


def test_builtin_plugin_failure_propagates(plugins_root: Path) -> None:
    """A builtin import failure is an in-tree bug and must be fatal."""
    _write_plugin(
        plugins_root, "bad", name="nexctf_bad", entry_points={"bad": "missing_mod"}
    )

    with pytest.raises(ModuleNotFoundError):
        loader._load_plugins_from_dir(plugins_root, is_builtin=True)


def test_already_loaded_entry_point_is_not_reimported(plugins_root: Path) -> None:
    """An entry-point name already loaded is skipped (first loader wins)."""
    sentinel = ModuleType("dup_sentinel")
    loader._loaded["dup"] = sentinel
    _write_module(plugins_root, "dup_mod")
    _write_plugin(
        plugins_root, "dup", name="nexctf_dup", entry_points={"dup": "dup_mod"}
    )

    loader._load_plugins_from_dir(plugins_root, is_builtin=True)

    assert loader._loaded["dup"] is sentinel
    assert "dup" not in loader._plugin_metadata


def test_missing_directory_is_noop() -> None:
    loader._load_plugins_from_dir(Path("/does/not/exist"), is_builtin=False)
    assert loader._plugin_metadata == {}
    assert loader._loaded == {}


def test_register_and_get_plugin_tables() -> None:
    loader.register_plugin_tables("a", "b")
    loader.register_plugin_tables("b", "c")
    tables = loader.get_plugin_tables()
    assert tables == frozenset({"a", "b", "c"})
    assert isinstance(tables, frozenset)


def test_derive_owned_tables_from_models() -> None:
    """Owned tables derive from the models' __tablename__, so plugin authors
    declare each table once (on the model) and never restate it in pyproject."""
    tables = loader.derive_owned_tables(
        [
            "nexctf.plugins.builtin.solution.mcq.model",
            "nexctf.plugins.builtin.solution.regex.model",
        ]
    )
    assert tables == frozenset({"solutions_mcq", "solutions_regex"})


def test_derive_owned_tables_empty_without_models() -> None:
    """A plugin that declares no model modules (e.g. a builtin core type whose
    tables live in the main schema) owns no separate tables to exclude."""
    assert loader.derive_owned_tables([]) == frozenset()


def test_load_builtin_plugins_registers_real_types() -> None:
    """Loading the in-tree builtin plugins registers their challenge/solution types."""
    from nexctf.plugins import challenge_registry, solution_registry

    loader.load_builtin_plugins()

    challenge_types = {name for name, _ in challenge_registry.items()}
    solution_types = {name for name, _ in solution_registry.items()}
    assert "standard" in challenge_types
    assert {"mcq", "regex", "match"} <= solution_types
    assert {"challenge", "solution"} <= set(loader._plugin_metadata)
