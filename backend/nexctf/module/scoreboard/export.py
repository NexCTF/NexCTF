"""Serialize the admin scoreboard to downloadable formats."""

import csv
import io
import json
from collections.abc import Callable, Sequence
from datetime import datetime
from enum import StrEnum
from typing import NamedTuple

from nexctf.bundle.slugs import slugify
from nexctf.exceptions import UnknownExportColumnError
from nexctf.schema import AdminScoreboard, AdminScoreboardEntry
from nexctf.schema.scoreboard import CUSTOM_COLUMN_PREFIX

# Characters that make a spreadsheet read a cell as a formula
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExportFormat(StrEnum):
    """Supported scoreboard export formats."""

    csv = "csv"
    json = "json"
    ctftime = "ctftime"


def _resolve_columns(board: AdminScoreboard, columns: Sequence[str]) -> list[str]:
    """Validate the requested columns; an empty request selects all of them."""
    allowed = board.export_columns
    if not columns:
        return allowed
    unknown = [c for c in columns if c not in allowed]
    if unknown:
        raise UnknownExportColumnError(detail=f"Unknown column: {', '.join(unknown)}")
    return list(dict.fromkeys(columns))


def _cell(entry: AdminScoreboardEntry, column: str) -> object:
    if column.startswith(CUSTOM_COLUMN_PREFIX):
        return entry.custom_fields.get(column.removeprefix(CUSTOM_COLUMN_PREFIX))
    return getattr(entry, column)


def _safe(value: object) -> str:
    """Stringify a cell and neutralize spreadsheet formula injection."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value)
    if isinstance(value, str) and text.startswith(_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def to_csv(board: AdminScoreboard, columns: Sequence[str] = ()) -> str:
    """Render the scoreboard as CSV with the selected columns, in request order."""
    selected = _resolve_columns(board, columns)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(selected)
    for entry in board.entries:
        writer.writerow(_safe(_cell(entry, c)) for c in selected)
    return buf.getvalue()


def to_ctftime(board: AdminScoreboard, columns: Sequence[str] = ()) -> str:
    """Render the scoreboard in the CTFtime scoreboard feed format."""
    standings = []
    for entry in board.entries:
        row: dict[str, object] = {
            "pos": entry.rank,
            "team": entry.team_name,
            "score": entry.total,
        }
        if entry.last_solve_at is not None:
            row["lastAccept"] = int(entry.last_solve_at.timestamp())
        standings.append(row)
    return json.dumps({"standings": standings}, indent=2, ensure_ascii=False)


def _to_json(board: AdminScoreboard, columns: Sequence[str] = ()) -> str:
    return board.model_dump_json(indent=2)


class _Spec(NamedTuple):
    render: Callable[[AdminScoreboard, Sequence[str]], str]
    media_type: str
    name: str


_SPECS: dict[ExportFormat, _Spec] = {
    ExportFormat.csv: _Spec(to_csv, "text/csv; charset=utf-8", "scoreboard.csv"),
    ExportFormat.json: _Spec(_to_json, "application/json", "scoreboard.json"),
    ExportFormat.ctftime: _Spec(
        to_ctftime, "application/json", "scoreboard-ctftime.json"
    ),
}


def render(
    board: AdminScoreboard, fmt: ExportFormat, columns: Sequence[str] = ()
) -> tuple[str, str]:
    """Return ``(content, media_type)``; ``columns`` only applies to CSV."""
    spec = _SPECS[fmt]
    return spec.render(board, columns), spec.media_type


def filename_for(fmt: ExportFormat, now: datetime, bracket: str | None) -> str:
    """Build a header-safe name such as ``scoreboard-20261101T120000Z.csv``."""
    stem, ext = _SPECS[fmt].name.rsplit(".", 1)
    slug = slugify(bracket or "", fallback="")
    suffix = f"-{slug}" if slug else ""
    return f"{stem}{suffix}-{now:%Y%m%dT%H%M%SZ}.{ext}"
