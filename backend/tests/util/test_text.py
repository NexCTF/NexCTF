"""Display-name normalisation."""

import pytest
from pydantic import TypeAdapter, ValidationError

from nexctf.schema.custom_field import CustomFieldValuesInput
from nexctf.schema.team import TeamName
from nexctf.schema.user import Username
from nexctf.util.text import normalize_name, sanitize_name

_username: TypeAdapter[str] = TypeAdapter(Username)
_team_name: TypeAdapter[str] = TypeAdapter(TeamName)
_values: TypeAdapter[dict] = TypeAdapter(CustomFieldValuesInput)


def test_compatibility_forms_fold_to_one_spelling() -> None:
    assert normalize_name("\uff41\uff44\uff4d\uff49\uff4e") == "admin"
    assert normalize_name("\ufb01sh") == "fish"


@pytest.mark.parametrize(
    "name",
    ["a\u200bb", "a\u202eb", "a\u2066b", "a\x00b", "a\nb", "a\u2028b", "\ufeffab"],
)
def test_invisible_and_control_characters_are_refused(name: str) -> None:
    with pytest.raises(ValueError):
        normalize_name(name)
    with pytest.raises(ValidationError):
        _username.validate_python(name)
    with pytest.raises(ValidationError):
        _team_name.validate_python(name)


def test_length_is_checked_after_normalisation() -> None:
    assert _username.validate_python("\ufb01" * 16) == "fi" * 16
    with pytest.raises(ValidationError):
        _username.validate_python("\ufb01" * 17)


def test_plain_unicode_names_are_kept() -> None:
    assert _team_name.validate_python("  Équipe 日本 🚩 ") == "Équipe 日本 🚩"


def test_sanitize_drops_and_truncates() -> None:
    assert sanitize_name("a\u200bb\u202e" + "c" * 40, 32) == "ab" + "c" * 30
    assert sanitize_name("\u200b\u200b", 32) == ""


def test_custom_field_values_are_stripped_and_bounded() -> None:
    key = "00000000-0000-0000-0000-000000000001"
    assert list(_values.validate_python({key: "  x "}).values()) == ["x"]
    assert list(_values.validate_python({key: " "}).values()) == [""]
    with pytest.raises(ValidationError):
        _values.validate_python({key: "x" * 256})
