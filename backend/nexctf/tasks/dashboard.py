"""The pgqueuer web dashboard, served by the API to admins only."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pgqueuer.adapters.web.sse import Broadcaster
from pgqueuer.db import AsyncpgDriver
from pgqueuer.types import Channel
from pgqueuer.web import create_web_router
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nexctf.api.dep import AdminAuthDep
from nexctf.core.db import db
from nexctf.tasks.queue import DB_SETTINGS, EngineDriver, build_queries, connect

DASHBOARD_PREFIX = "/api/admin/tasks"
# Only same-origin pages, i.e. the admin UI, may frame the dashboard.
_FRAME_POLICY = (b"content-security-policy", b"frame-ancestors 'self'")


class _SameOriginFramesOnly:
    """Forbid framing the dashboard's responses from another origin."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(DASHBOARD_PREFIX):
            await self.app(scope, receive, send)
            return

        async def send_with_policy(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", ()), _FRAME_POLICY]
            await send(message)

        await self.app(scope, receive, send_with_policy)


def install_dashboard(app: FastAPI) -> None:
    """Mount the dashboard under ``DASHBOARD_PREFIX``, on the app's own pool."""
    app.state.pgq_queries = build_queries(EngineDriver(db.engine))
    app.include_router(
        create_web_router(dependencies=[AdminAuthDep]),
        prefix=DASHBOARD_PREFIX,
        include_in_schema=False,
    )
    app.add_middleware(_SameOriginFramesOnly)


@asynccontextmanager
async def live_dashboard(app: FastAPI) -> AsyncGenerator[None]:
    """Push queue changes to open dashboards, over one LISTEN connection.

    Should that connection drop, the dashboard pages fall back to polling.
    """
    conn = await connect()
    try:
        app.state.pgq_broadcaster = Broadcaster(
            driver=AsyncpgDriver(conn), channel=Channel(DB_SETTINGS.channel)
        )
        await app.state.pgq_broadcaster.start()
        yield
    finally:
        await conn.close()
