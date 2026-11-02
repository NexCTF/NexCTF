"""Tests for the scoreboard export serializers."""

import csv
import io
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from nexctf.exceptions import UnknownExportColumnError
from nexctf.module.scoreboard import export
from nexctf.schema import AdminScoreboard, AdminScoreboardEntry, ScoreboardCustomField

SOLVED_AT = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


_DEFAULTS: dict[str, object] = {
    "team_bracket": None,
    "total": 100,
    "solve_points": 100,
    "adjustment_points": 0,
    "hint_points": 0,
    "solve_count": 1,
    "last_solve_at": SOLVED_AT,
}


def _entry(rank: int, name: str, **kw: object) -> AdminScoreboardEntry:
    data = {**_DEFAULTS, "rank": rank, "team_id": uuid4(), "team_name": name, **kw}
    return AdminScoreboardEntry.model_validate(data)


def _board(*entries: AdminScoreboardEntry) -> AdminScoreboard:
    return AdminScoreboard(
        entries=list(entries),
        computed_at=SOLVED_AT,
        custom_fields=[ScoreboardCustomField(name="country", label="Country")],
    )


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


class TestCsv:
    def test_all_columns_by_default(self) -> None:
        rows = _rows(
            export.to_csv(_board(_entry(1, "A", custom_fields={"country": "FR"})))
        )
        assert rows[0] == _board().export_columns
        assert rows[0][-1] == "custom.country"
        assert rows[1][-1] == "FR"

    def test_selected_columns_keep_request_order(self) -> None:
        board = _board(_entry(1, "A", total=300))
        rows = _rows(export.to_csv(board, ["total", "team_name", "total"]))
        assert rows == [["total", "team_name"], ["300", "A"]]

    def test_unknown_column_rejected(self) -> None:
        with pytest.raises(UnknownExportColumnError):
            export.to_csv(_board(), ["password"])

    @pytest.mark.parametrize("name", ["=1+1", "+cmd", "-2", "@SUM(A1)", "\tx"])
    def test_formula_injection_neutralized(self, name: str) -> None:
        rows = _rows(export.to_csv(_board(_entry(1, name)), ["team_name"]))
        assert rows[1] == [f"'{name}"]

    def test_negative_numbers_not_escaped(self) -> None:
        board = _board(_entry(1, "A", adjustment_points=-20))
        rows = _rows(export.to_csv(board, ["adjustment_points"]))
        assert rows[1] == ["-20"]

    def test_missing_values_are_empty(self) -> None:
        board = _board(_entry(1, "A", last_solve_at=None))
        rows = _rows(
            export.to_csv(board, ["team_bracket", "last_solve_at", "custom.country"])
        )
        assert rows[1] == ["", "", ""]


class TestCtftime:
    def test_standings_shape(self) -> None:
        board = _board(_entry(1, "A", total=200), _entry(2, "B", last_solve_at=None))
        data = json.loads(export.to_ctftime(board))
        assert data == {
            "standings": [
                {
                    "pos": 1,
                    "team": "A",
                    "score": 200,
                    "lastAccept": int(SOLVED_AT.timestamp()),
                },
                {"pos": 2, "team": "B", "score": 100},
            ]
        }


class TestFilename:
    def test_bracket_is_header_safe(self) -> None:
        name = export.filename_for(export.ExportFormat.csv, SOLVED_AT, 'uni "x"\r\n')
        assert name == "scoreboard-uni-x-20261101T120000Z.csv"

    def test_ctftime_name(self) -> None:
        name = export.filename_for(export.ExportFormat.ctftime, SOLVED_AT, None)
        assert name == "scoreboard-ctftime-20261101T120000Z.json"
