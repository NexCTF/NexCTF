"""Unicode clean-up for player-chosen display names."""

import unicodedata

from pydantic import BeforeValidator

# Control, format, surrogate, private-use and unassigned code points, plus the
# line and paragraph separators
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


def _is_forbidden(char: str) -> bool:
    return unicodedata.category(char) in _FORBIDDEN_CATEGORIES


def normalize_name(value: str) -> str:
    """NFKC-normalise *value*, refusing invisible and control characters."""
    normalized = unicodedata.normalize("NFKC", value)
    if any(_is_forbidden(char) for char in normalized):
        raise ValueError("control and invisible characters are not allowed")
    return normalized


def sanitize_name(value: str, max_length: int) -> str:
    """NFKC-normalise *value*, dropping what ``normalize_name`` refuses."""
    normalized = unicodedata.normalize("NFKC", value)
    kept = "".join(char for char in normalized if not _is_forbidden(char))
    return kept.strip()[:max_length].strip()


# Pydantic annotation applying ``normalize_name`` before the type's own checks
NormalizedName = BeforeValidator(
    lambda value: normalize_name(value) if isinstance(value, str) else value
)
