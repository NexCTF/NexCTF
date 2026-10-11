"""Prometheus scrape endpoint."""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi_toolsets.exceptions import init_exceptions_handlers
from httpx import ASGITransport, AsyncClient
from pgqueuer import Queries
from pgqueuer.ports.repository import EntrypointExecutionParameter
from pgqueuer.types import QueueEntrypoint, QueueManagerId
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.metrics import metrics_router
from nexctf.core.cache import get_redis
from nexctf.core.config import settings
from nexctf.core.db import db
from nexctf.model import Event, Question, Submission
from nexctf.module.session import FAILED_LOGIN_EVENT
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from tests.base import make_team, make_user

COUNTERS = {"rate_limited:submit": "3", "emails:sent": "2"}


@pytest.fixture
async def metrics_client(
    db_session: AsyncSession, task_queue: Queries, mock_redis: AsyncMock
) -> AsyncIterator[AsyncClient]:
    """Client for an app serving only the metrics router on the test session."""
    app = FastAPI()
    app.include_router(metrics_router)
    init_exceptions_handlers(app=app)

    async def _db() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def _redis() -> AsyncIterator[AsyncMock]:
        yield mock_redis

    app.dependency_overrides[db] = _db
    app.dependency_overrides[get_redis] = _redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def _seed(db_session: AsyncSession) -> None:
    """One team that solved a two-question challenge, and one that did not."""
    solver = await make_team(db_session, "solver")
    other = await make_team(db_session, "other")
    await make_user(db_session, "metrics-user", solver)
    db_session.add(
        Event(event_type=FAILED_LOGIN_EVENT, meta={"reason": "bad_password"})
    )
    challenge = StandardChallenge(title="Metrics", category="web", is_active=True)
    db_session.add(challenge)
    await db_session.flush()
    first = Question(label="Q1", challenge_id=challenge.id)
    second = Question(label="Q2", challenge_id=challenge.id, index=1)
    db_session.add_all([first, second])
    await db_session.flush()
    db_session.add_all(
        [
            Submission(answer="a", is_correct=True, team=solver, question=first),
            Submission(answer="b", is_correct=True, team=solver, question=second),
            Submission(answer="c", is_correct=True, team=other, question=first),
            Submission(answer="d", team=other, question=second),
        ]
    )
    await db_session.flush()


async def _run_job(task_queue: Queries, entrypoint: str) -> None:
    """Take one job through the queue: enqueue, pick, then finish it."""
    await task_queue.enqueue(entrypoint, None)
    [job] = await task_queue.dequeue(
        batch_size=1,
        entrypoints={
            QueueEntrypoint(entrypoint): EntrypointExecutionParameter(
                concurrency_limit=0
            )
        },
        queue_manager_id=QueueManagerId(uuid.uuid4()),
        global_concurrency_limit=None,
        heartbeat_timeout=timedelta(seconds=30),
    )
    await task_queue.log_jobs([(job, "successful", None)])


async def test_metrics_exposes_counts(
    metrics_client: AsyncClient,
    db_session: AsyncSession,
    task_queue: Queries,
    mock_redis: AsyncMock,
) -> None:
    await _seed(db_session)
    await task_queue.enqueue("metrics_demo", None)
    await _run_job(task_queue, "metrics_done")
    mock_redis.hgetall = AsyncMock(
        side_effect=lambda key: COUNTERS if key == "metrics:counters" else {}
    )

    resp = await metrics_client.get("/metrics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    for line in (
        'nexctf_users{role="user"} 1.0',
        'nexctf_users{role="admin"} 0.0',
        "nexctf_teams 2.0",
        'nexctf_challenges{active="true"} 1.0',
        'nexctf_submissions_total{correct="true"} 3.0',
        'nexctf_submissions_total{correct="false"} 1.0',
        'nexctf_challenge_solves{category="web",challenge="Metrics"} 1.0',
        "nexctf_hint_unlocks_total 0.0",
        "nexctf_active_sessions 0.0",
        'nexctf_queue_jobs{entrypoint="metrics_demo",status="queued"} 1.0',
        'nexctf_queue_jobs_finished_recent{entrypoint="metrics_done",status="successful"} 1.0',
        'nexctf_queue_job_duration_avg_seconds{entrypoint="metrics_done",status="successful"}',
        'nexctf_queue_job_duration_max_seconds{entrypoint="metrics_done",status="successful"}',
        'nexctf_ctf_phase{phase="running"} 1.0',
        'nexctf_rate_limited_total{limit="submit"} 3.0',
        'nexctf_emails_total{result="sent"} 2.0',
        'nexctf_login_failures_total{reason="bad_password"} 1.0',
        "nexctf_build_info{version=",
    ):
        assert line in body, line


@pytest.mark.parametrize(
    ("header", "status"),
    [(None, 401), ("Bearer wrong", 401), ("Bearer s3cret", 200)],
)
async def test_metrics_token(
    metrics_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    header: str | None,
    status: int,
) -> None:
    monkeypatch.setattr(settings, "METRICS_TOKEN", "s3cret")
    headers = {"Authorization": header} if header else {}
    resp = await metrics_client.get("/metrics", headers=headers)
    assert resp.status_code == status
