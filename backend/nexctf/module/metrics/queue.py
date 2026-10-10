"""Background task queue depth and recent job outcomes."""

from __future__ import annotations

from collections import Counter

from prometheus_client.core import GaugeMetricFamily, Metric
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.tasks.queue import DB_SETTINGS, SessionDriver, build_queries

RECENT_WINDOW_MINUTES = 15

_LOG = DB_SETTINGS.qualified.queue_table_log

_RECENT = text(
    "SELECT f.entrypoint, f.status::text, count(*),"
    " avg(extract(epoch FROM f.created - p.created)),"
    " max(extract(epoch FROM f.created - p.created))"
    f" FROM {_LOG} f LEFT JOIN LATERAL ("
    f"  SELECT created FROM {_LOG} p"
    "   WHERE p.job_id = f.job_id AND p.status = 'picked' AND p.created <= f.created"
    "   AND f.status IN ('successful', 'exception')"
    "   ORDER BY p.created DESC LIMIT 1"
    " ) p ON true"
    " WHERE f.created > now() - make_interval(mins => :minutes)"
    " AND f.status IN ('successful', 'exception', 'canceled', 'deleted')"
    " GROUP BY f.entrypoint, f.status"
)


async def _depth(session: AsyncSession) -> Metric:
    """Jobs in the queue table, by entrypoint and status."""
    jobs = GaugeMetricFamily(
        "nexctf_queue_jobs",
        "Background jobs in the task queue.",
        labels=["entrypoint", "status"],
    )
    counts: Counter[tuple[str, str]] = Counter()
    for stat in await build_queries(SessionDriver(session)).queue_size():
        counts[(stat.entrypoint, stat.status)] += stat.count
    for labels, count in sorted(counts.items()):
        jobs.add_metric(list(labels), count)
    return jobs


async def _recent(session: AsyncSession) -> list[Metric]:
    """Jobs finished within the recent window, with their run times."""
    labels = ["entrypoint", "status"]
    window = f"in the last {RECENT_WINDOW_MINUTES} minutes"
    finished = GaugeMetricFamily(
        "nexctf_queue_jobs_finished_recent", f"Jobs finished {window}.", labels=labels
    )
    avg = GaugeMetricFamily(
        "nexctf_queue_job_duration_avg_seconds",
        f"Mean run time of jobs finished {window}.",
        labels=labels,
    )
    peak = GaugeMetricFamily(
        "nexctf_queue_job_duration_max_seconds",
        f"Longest run time of jobs finished {window}.",
        labels=labels,
    )
    rows = await session.execute(_RECENT, {"minutes": RECENT_WINDOW_MINUTES})
    for entrypoint, status, count, mean, longest in rows:
        finished.add_metric([entrypoint, status], count)
        if mean is not None:
            avg.add_metric([entrypoint, status], float(mean))
            peak.add_metric([entrypoint, status], float(longest))
    return [finished, avg, peak]


async def queue_metrics(session: AsyncSession) -> list[Metric]:
    """Queue depth, recent outcomes and recent run times."""
    return [await _depth(session), *await _recent(session)]
