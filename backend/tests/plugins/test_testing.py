"""Tests for the plugin test helpers in :mod:`nexctf.plugins.testing`.

These exercise the helpers against the in-tree builtins so the helpers a plugin
author relies on are themselves covered.
"""

from __future__ import annotations

import pytest

from nexctf.plugins import challenge_registry, load_builtin_plugins, solution_registry
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.regex.model import RegexSolution
from nexctf.plugins.testing import assert_registered, assert_verifies


async def test_assert_verifies_runs_each_case() -> None:
    """A real, deterministic solution verifies matching and non-matching input."""
    solution = RegexSolution(pattern=r"flag\{.*\}")
    await assert_verifies(solution, [("flag{ok}", True), ("nope", False)])


async def test_assert_verifies_raises_on_unexpected_result() -> None:
    """The helper fails loudly when verify disagrees with the expected bool."""
    solution = RegexSolution(pattern=r"flag\{.*\}")
    with pytest.raises(AssertionError):
        await assert_verifies(solution, [("flag{ok}", False)])


def test_assert_registered_matches_builtin_solution() -> None:
    load_builtin_plugins()
    assert_registered(solution_registry, "regex", model=RegexSolution)


def test_assert_registered_matches_builtin_challenge() -> None:
    """Challenge support is registration validation (hook behaviour is plugin-specific)."""
    load_builtin_plugins()
    assert_registered(challenge_registry, "standard", model=StandardChallenge)


def test_assert_registered_raises_for_unknown_type() -> None:
    with pytest.raises(AssertionError):
        assert_registered(solution_registry, "does-not-exist")


def test_assert_registered_raises_on_wrong_model() -> None:
    load_builtin_plugins()
    with pytest.raises(AssertionError):
        assert_registered(solution_registry, "regex", model=StandardChallenge)
