"""Unit tests for nexctf.module.info.version semver comparison."""

import pytest

from nexctf.module.info.version import _parse


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        ("0.4.0", "0.4.0", False),
        ("0.4.0", "0.5.0", True),
        ("0.4.0", "v0.5.0", True),
        ("0.4.0", "0.3.9", False),
        ("0.9.0", "0.10.0", True),
    ],
)
def test_update_available(current: str, latest: str, expected: bool) -> None:
    assert (_parse(latest) > _parse(current)) is expected
