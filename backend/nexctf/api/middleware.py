"""ASGI middleware binding the request context every log record carries."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nexctf.core.logging import ACCESS_LOGGER, log_context
from nexctf.util.ip import get_client_ip

logger = logging.getLogger(ACCESS_LOGGER)


class RequestContextMiddleware:
    """Bind a request id and client IP, then log one access line per request.

    Runs as raw ASGI rather than ``BaseHTTPMiddleware`` so streaming responses
    (SSE) keep their own task and cancellation.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex[:16]
        ip = get_client_ip(Request(scope))
        started = time.perf_counter()
        status = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        with log_context(request_id=request_id, ip=ip):
            try:
                await self.app(scope, receive, send_with_request_id)
            finally:
                method = scope.get("method", "")
                path = scope.get("path", "")
                duration_ms = round((time.perf_counter() - started) * 1000, 1)
                logger.info(
                    "request",
                    extra={
                        "method": method,
                        "path": path,
                        "status": status,
                        "duration_ms": duration_ms,
                    },
                )
