"""Tests for the pgqueuer dashboard the API serves to admins."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import AsyncIterator
from functools import partial

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from httpx import AsyncClient
from pgqueuer import Queries
from pgqueuer.models import TracebackRecord
from sqlalchemy.ext.asyncio import create_async_engine

from nexctf.main import app
from nexctf.model import User
from nexctf.tasks import dashboard
from nexctf.tasks.dashboard import DASHBOARD_PREFIX, live_dashboard
from nexctf.tasks.queue import EngineDriver, build_queries, connect

# The dashboard sits at the app root, not under the clients' /api/v1 base_url.
_ROOT = f"http://127.0.0.1{DASHBOARD_PREFIX}"
_PAGES = [
    "/",
    "/entrypoints",
    "/jobs",
    "/failures",
    "/workers",
    "/schedules",
    "/system",
]


@pytest.fixture
async def dashboard_queue(
    task_queue: Queries, task_queue_schema: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Queries]:
    """Serve the dashboard from the emptied test queue, over its production driver."""
    engine = create_async_engine(task_queue_schema)
    queries = build_queries(EngineDriver(engine))
    monkeypatch.setattr(app.state, "pgq_queries", queries, raising=False)
    try:
        yield task_queue
    finally:
        await engine.dispose()


async def _held_failure(queries: Queries) -> int:
    """Queue a job, then hold it as failed with its traceback logged."""
    (job_id,) = await queries.enqueue("dashboard_job", b"{}")
    job = await queries.queue_job_by_id(job_id)
    assert job is not None
    record = TracebackRecord.from_exception(ValueError("boom"), job_id)
    await queries.log_jobs([(job, "failed", record)])
    return job_id


async def test_dashboard_rejects_anonymous(http_client: AsyncClient) -> None:
    assert (await http_client.get(f"{_ROOT}/")).status_code == 401
    assert (await http_client.get(f"{_ROOT}/events")).status_code == 401


async def test_dashboard_rejects_regular_user(
    user_client: tuple[AsyncClient, User],
) -> None:
    c, _ = user_client
    assert (await c.get(f"{_ROOT}/")).status_code == 403


@pytest.mark.parametrize("page", _PAGES)
async def test_dashboard_pages_render_for_admin(
    admin_client: tuple[AsyncClient, User], dashboard_queue: Queries, page: str
) -> None:
    await dashboard_queue.enqueue("dashboard_job", b"{}")
    await _held_failure(dashboard_queue)
    c, _ = admin_client
    resp = await c.get(f"{_ROOT}{page}")
    assert resp.status_code == 200
    assert f'href="{_ROOT}/static/style.css"' in resp.text
    assert f'sse-connect="{_ROOT}/events"' in resp.text
    assert resp.headers["content-security-policy"] == "frame-ancestors 'self'"


async def test_dashboard_requeues_a_held_failure(
    admin_client: tuple[AsyncClient, User], dashboard_queue: Queries
) -> None:
    job_id = await _held_failure(dashboard_queue)
    c, _ = admin_client
    detail = await c.get(f"{_ROOT}/jobs/{job_id}")
    assert detail.status_code == 200
    assert "ValueError" in detail.text

    resp = await c.post(
        f"{_ROOT}/jobs/requeue",
        data={"ids": str(job_id)},
        headers={"sec-fetch-site": "same-origin"},
    )
    assert resp.status_code == 204
    assert await dashboard_queue.queue_size()


async def test_dashboard_refuses_cross_site_actions(
    admin_client: tuple[AsyncClient, User], dashboard_queue: Queries
) -> None:
    job_id = await _held_failure(dashboard_queue)
    c, _ = admin_client
    resp = await c.post(
        f"{_ROOT}/jobs/requeue",
        data={"ids": str(job_id)},
        headers={"sec-fetch-site": "cross-site"},
    )
    assert resp.status_code == 403


def test_dashboard_route_names_are_unique() -> None:
    """Every dashboard route name resolves to that route alone."""
    contexts = list(iter_route_contexts(app.routes))
    names = Counter(getattr(ctx.route, "name", None) for ctx in contexts)
    dashboard = [
        getattr(ctx.route, "name", None)
        for ctx in contexts
        if (ctx.path or "").startswith(DASHBOARD_PREFIX)
    ]
    assert dashboard
    assert all(names[name] == 1 for name in dashboard)


def test_dashboard_is_left_out_of_the_api_schemas() -> None:
    assert not [p for p in app.openapi()["paths"] if p.startswith(DASHBOARD_PREFIX)]


async def test_live_dashboard_pushes_queue_changes(
    task_queue: Queries, task_queue_schema: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dashboard, "connect", partial(connect, task_queue_schema))
    scratch = FastAPI()
    async with live_dashboard(scratch):
        stream = scratch.state.pgq_broadcaster.stream()
        assert await anext(stream) == "retry: 3000\n\n"
        pending = asyncio.ensure_future(anext(stream))
        await task_queue.enqueue("dashboard_job", None)
        frame = await asyncio.wait_for(pending, timeout=5)
        await stream.aclose()
    assert frame.startswith("event: queue-change\n")
