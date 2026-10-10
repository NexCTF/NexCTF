"""Configured event times and the phase the event is in."""

from __future__ import annotations

from datetime import UTC, datetime

from prometheus_client.core import GaugeMetricFamily, Metric

from nexctf.util.datetime import parse_config_dt

_PHASES = ("not_started", "running", "frozen", "ended")

_TIMES = {
    "start": "ctf.start_time",
    "end": "ctf.end_time",
    "freeze": "ctf.freeze_time",
}


def _phase(times: dict[str, datetime | None]) -> str:
    """The phase the event is in, given its configured times."""
    now = datetime.now(UTC)
    start, end, freeze = times["start"], times["end"], times["freeze"]
    if end and now > end:
        return "ended"
    if freeze and now > freeze:
        return "frozen"
    if start and now < start:
        return "not_started"
    return "running"


def competition_metrics(overrides: dict[str, str]) -> list[Metric]:
    """Event start, end and freeze times, and the current phase."""
    times = {name: parse_config_dt(key, overrides) for name, key in _TIMES.items()}
    timestamps = GaugeMetricFamily(
        "nexctf_ctf_time_seconds",
        "Configured event times as Unix timestamps; unset times are omitted.",
        labels=["time"],
    )
    for name, moment in times.items():
        if moment is not None:
            timestamps.add_metric([name], moment.timestamp())

    current = _phase(times)
    phase = GaugeMetricFamily(
        "nexctf_ctf_phase", "1 for the phase the event is in.", labels=["phase"]
    )
    for name in _PHASES:
        phase.add_metric([name], 1 if name == current else 0)
    return [timestamps, phase]
