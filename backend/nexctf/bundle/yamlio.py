"""Byte-stable YAML and markdown serialization."""

from __future__ import annotations

from typing import Any

import yaml

from nexctf.bundle.errors import BundleFormatError

ENCODING = "utf-8"


class _Dumper(yaml.SafeDumper):
    """SafeDumper that never emits anchors, so repeated values stay inline."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def _block_safe(text: str) -> bool:
    """True when a literal block scalar round-trips the string unchanged."""
    lines = text.split("\n")
    return (
        "\r" not in text
        and not text.startswith((" ", "\t"))
        and all(line == line.rstrip() for line in lines)
        and not text.endswith("\n")
    )


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Emit multi-line strings as literal blocks when that is lossless."""
    style = "|" if "\n" in data and _block_safe(data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str_representer)


class ConfigValue(str):
    """A config value, quoted on output so every entry in the file looks alike."""


def _config_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Quote a config value, unless it needs a block scalar to stay lossless."""
    if "\n" in data:
        return _str_representer(dumper, str(data))
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")


_Dumper.add_representer(ConfigValue, _config_representer)


def _normalize(text: str, *, rstrip_lines: bool) -> str:
    """LF endings, optional per-line rstrip, exactly one trailing newline."""
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = body.split("\n")
    if rstrip_lines:
        lines = [line.rstrip() for line in lines]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


def dump_yaml(data: dict[str, Any]) -> bytes:
    """Serialize a mapping of primitives to deterministic YAML bytes."""
    text = yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1_000_000,
    )
    return _normalize(text, rstrip_lines=True).encode(ENCODING)


def load_yaml(raw: bytes) -> dict[str, Any]:
    """Parse YAML bytes into a mapping, treating an empty document as ``{}``.

    Raises:
        BundleFormatError: If the document is not a mapping.
    """
    data = yaml.safe_load(raw.decode(ENCODING)) or {}
    if not isinstance(data, dict):
        raise BundleFormatError("expected a YAML mapping")
    return data


def dump_markdown(text: str) -> bytes:
    """Serialize a long-text field to its ``.md`` sibling."""
    return _normalize(text, rstrip_lines=False).encode(ENCODING)


def load_markdown(raw: bytes) -> str:
    """Read a ``.md`` sibling back, normalized the same way it was written."""
    return _normalize(raw.decode(ENCODING), rstrip_lines=False)


def normalize_long_text(text: str | None) -> str | None:
    """Apply the ``.md`` normalization to a value still held in the IR.

    Export runs every long-text field through this so a round trip compares
    equal to what the writer would have emitted.
    """
    return None if text is None else _normalize(text, rstrip_lines=False)


def ordered(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Project a mapping onto ``keys``, in that order, dropping absent ones."""
    return {key: data[key] for key in keys if key in data}
