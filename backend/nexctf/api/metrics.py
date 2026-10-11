"""Prometheus scrape endpoint, mounted outside the API prefix."""

import secrets
from collections.abc import Iterable
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response
from fastapi_toolsets.exceptions import UnauthorizedError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_client.core import Metric
from prometheus_client.registry import Collector

from nexctf.api.dep import RedisDep, SessionDep
from nexctf.core.config import settings
from nexctf.module.metrics import collect_metrics


def _require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    """Reject the scrape unless it carries ``METRICS_TOKEN`` as a bearer token."""
    if not settings.METRICS_TOKEN:
        return
    expected = f"Bearer {settings.METRICS_TOKEN}".encode()
    if not secrets.compare_digest((authorization or "").encode(), expected):
        raise UnauthorizedError()


metrics_router = APIRouter(dependencies=[Depends(_require_token)])


class _Snapshot(Collector):
    """Collector serving metric families that were already read."""

    def __init__(self, metrics: list[Metric]) -> None:
        self._metrics = metrics

    def collect(self) -> Iterable[Metric]:
        return self._metrics


@metrics_router.get("/metrics", include_in_schema=False)
async def metrics(session: SessionDep, redis: RedisDep) -> Response:
    """Expose the NexCTF metrics in the Prometheus text format."""
    output = generate_latest(_Snapshot(await collect_metrics(session, redis)))
    return Response(output, media_type=CONTENT_TYPE_LATEST)
