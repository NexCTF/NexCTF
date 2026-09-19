"""Directory naming for the tree serialization."""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_MAX_SLUG = 64


def slugify(value: str, *, fallback: str = "item") -> str:
    """Lowercase ASCII slug, hyphen-separated, bounded in length."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = _NON_SLUG.sub("-", ascii_only.lower()).strip("-")[:_MAX_SLUG].strip("-")
    return slug or fallback


def unique_slugs(items: list[tuple[UUID, str]]) -> dict[UUID, str]:
    """Map each id to a slug, disambiguating collisions deterministically.

    Args:
        items: ``(id, title)`` pairs, already in the order they are written.

    Returns:
        A mapping of id to a slug unique within the set. Colliding titles keep
        the first occurrence's plain slug; the rest carry an id suffix, so the
        result depends only on the ids and titles, never on iteration order.
    """
    taken: dict[str, UUID] = {}
    result: dict[UUID, str] = {}
    for entity_id, title in sorted(
        items, key=lambda pair: (slugify(pair[1]), str(pair[0]))
    ):
        slug = slugify(title)
        if slug in taken:
            slug = f"{slug}-{str(entity_id)[:8]}"
        taken[slug] = entity_id
        result[entity_id] = slug
    return result


def sanitize_filename(name: str) -> str:
    """Reduce a user-supplied filename to a safe basename for the tree."""
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(c for c in basename if c.isprintable() and c not in '<>:"|?*')
    cleaned = cleaned.strip().strip(".")
    return cleaned[:_MAX_SLUG] or "blob"
