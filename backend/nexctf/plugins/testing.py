"""Test helpers for plugin authors.

Import these from your plugin's tests to exercise registered solution and
challenge types without spinning up the full app or a database::

    from nexctf.plugins.testing import assert_registered, assert_verifies

These are plain ``assert``-based helpers (no pytest dependency), so they can be
used from any test runner.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from nexctf.model.solution import Solution
from nexctf.plugins.registry import PolymorphicRegistry, RegistryEntry, SchemaClass

__all__ = ["assert_registered", "assert_verifies"]


async def assert_verifies(
    solution: Solution,
    cases: Iterable[tuple[str, bool]],
    *,
    team_id: UUID | None = None,
) -> None:
    """Assert ``solution.verify()`` returns the expected result for each case.

    Args:
        solution: A solution model instance (constructed transiently — no
            database session is required).
        cases: ``(submission, expected)`` pairs; each submission is verified and
            compared against the expected boolean.
        team_id: Optional team context forwarded to ``verify`` for solution
            types that use it (e.g. a script checker).
    """
    for submission, expected in cases:
        result = await solution.verify(submission, team_id=team_id)
        assert bool(result) == expected, (
            f"verify({submission!r}) returned {result!r}, expected {expected!r}"
        )


def assert_registered(
    registry: PolymorphicRegistry,
    type_name: str,
    *,
    model: type | None = None,
    create_schema: SchemaClass | None = None,
    update_schema: SchemaClass | None = None,
    read_schema: SchemaClass | None = None,
) -> RegistryEntry:
    """Assert a polymorphic type is registered and wired to the given model/schemas.

    Pass the registry your plugin registered with (``solution_registry`` or
    ``challenge_registry``). Any argument left as ``None`` is not checked.

    Args:
        registry: The registry to look the type up in.
        type_name: The polymorphic type name the plugin registered under.
        model: Expected SQLAlchemy model bound to this type, if given.
        create_schema: Expected create schema, if given.
        update_schema: Expected update schema, if given.
        read_schema: Expected read schema, if given.

    Returns:
        The matched registry entry, for further assertions.

    Raises:
        AssertionError: If the type is not registered or a given expectation
            does not match.
    """
    try:
        entry = registry.get(type_name)
    except KeyError:
        raise AssertionError(f"type {type_name!r} is not registered") from None
    if model is not None:
        assert entry.crud.model is model, (
            f"type {type_name!r} is bound to {entry.crud.model!r}, expected {model!r}"
        )
    if create_schema is not None:
        assert entry.create_schema is create_schema, (
            f"type {type_name!r}: create_schema is {entry.create_schema!r}, expected {create_schema!r}"
        )
    if update_schema is not None:
        assert entry.update_schema is update_schema, (
            f"type {type_name!r}: update_schema is {entry.update_schema!r}, expected {update_schema!r}"
        )
    if read_schema is not None:
        assert entry.read_schema is read_schema, (
            f"type {type_name!r}: read_schema is {entry.read_schema!r}, expected {read_schema!r}"
        )
    return entry
