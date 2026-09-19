"""The all-in-one archive: the tree, zipped."""

from __future__ import annotations

import io
import zipfile

from nexctf.bundle.errors import BundleFormatError

_FIXED_DATE = (1980, 1, 1, 0, 0, 0)
_NOISE_DIRS = frozenset({"__MACOSX"})
_NOISE_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
MAX_ENTRIES = 50_000
MAX_UNCOMPRESSED = 2 * 1024**3


def write_archive(tree: dict[str, bytes]) -> bytes:
    """Zip a tree into deterministic archive bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(tree):
            info = zipfile.ZipInfo(path, date_time=_FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, tree[path])
    return buffer.getvalue()


def read_archive(data: bytes) -> dict[str, bytes]:
    """Read archive bytes back into a tree, refusing unsafe or oversized members.

    Raises:
        BundleFormatError: If the data is not a zip, escapes the tree root, or
            exceeds the entry-count or uncompressed-size limits.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BundleFormatError(f"not a zip archive: {exc}") from exc

    with archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) > MAX_ENTRIES:
            raise BundleFormatError(f"archive holds more than {MAX_ENTRIES} entries")
        if sum(info.file_size for info in members) > MAX_UNCOMPRESSED:
            raise BundleFormatError("archive expands beyond the size limit")
        tree = {
            _safe_path(info.filename): archive.read(info)
            for info in members
            if not _is_noise(info.filename)
        }
    return _unwrap(tree)


def _is_noise(name: str) -> bool:
    """True for a file a desktop zip tool added rather than the author."""
    parts = name.replace("\\", "/").split("/")
    return parts[-1] in _NOISE_NAMES or bool(_NOISE_DIRS.intersection(parts))


def _unwrap(tree: dict[str, bytes]) -> dict[str, bytes]:
    """Drop a single wrapping directory, if every path sits under the same one."""
    while tree and all("/" in path for path in tree):
        roots = {path.split("/", 1)[0] for path in tree}
        if len(roots) != 1:
            break
        tree = {path.split("/", 1)[1]: raw for path, raw in tree.items()}
    return tree


def _safe_path(name: str) -> str:
    """Refuse absolute paths, drive letters and any ``..`` traversal."""
    path = name.replace("\\", "/")
    parts = path.split("/")
    if path.startswith("/") or ":" in parts[0] or any(p == ".." for p in parts):
        raise BundleFormatError(f"unsafe path in archive: {name!r}")
    return path
