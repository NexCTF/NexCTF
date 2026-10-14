"""Tests for the event time helpers."""

import pytest

from nexctf.util.datetime import event_time_errors

START = "2099-01-01T00:00:00+00:00"
FREEZE = "2099-01-02T00:00:00+00:00"
END = "2099-01-03T00:00:00+00:00"


def _times(start: str, freeze: str, end: str) -> dict[str, str]:
    return {"ctf.start_time": start, "ctf.freeze_time": freeze, "ctf.end_time": end}


def test_ordered_times_pass() -> None:
    assert event_time_errors(_times(START, FREEZE, END)) == []


def test_unset_times_pass() -> None:
    assert event_time_errors(_times("", "", END)) == []


@pytest.mark.parametrize(
    ("times", "error"),
    [
        (_times(END, "", START), "ctf.end_time: must be after ctf.start_time"),
        (_times(START, "", START), "ctf.end_time: must be after ctf.start_time"),
        (_times(FREEZE, START, END), "ctf.freeze_time: must be after ctf.start_time"),
        (_times(START, END, FREEZE), "ctf.end_time: must be after ctf.freeze_time"),
    ],
)
def test_out_of_order_times_fail(times: dict[str, str], error: str) -> None:
    assert error in event_time_errors(times)


def test_naive_times_compare_as_utc() -> None:
    times = _times("2099-01-01T00:00:00", "", "2099-01-01T00:30:00+01:00")
    assert event_time_errors(times) == ["ctf.end_time: must be after ctf.start_time"]


def test_malformed_time_is_ignored() -> None:
    assert event_time_errors(_times("not-a-date", "", END)) == []
