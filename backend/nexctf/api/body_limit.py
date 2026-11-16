"""Request body size limit, enforced before the body is buffered."""

from collections.abc import Sequence

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nexctf.api.errors import api_error_response
from nexctf.exceptions import RequestTooLargeError

_UPLOAD_METHODS = frozenset({"POST", "PUT"})


def _declared_length(scope: Scope) -> int | None:
    """The request's Content-Length, or None when absent or malformed."""
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class _Guard:
    """Counts one request's streamed body and swaps in a 413 once it overflows."""

    def __init__(self, scope: Scope, receive: Receive, send: Send, limit: int) -> None:
        self.scope = scope
        self._receive = receive
        self._send = send
        self.limit = limit
        self.seen = 0
        self.overflowed = False
        self.refused = False

    async def receive(self) -> Message:
        """Pass a message through, raising once the body exceeds the limit."""
        message = await self._receive()
        if message["type"] == "http.request":
            self.seen += len(message.get("body", b""))
            if self.seen > self.limit:
                self.overflowed = True
                raise RequestTooLargeError()
        return message

    async def send(self, message: Message) -> None:
        """Forward the response, replaced by the refusal after an overflow."""
        if not self.overflowed:
            await self._send(message)
        elif not self.refused:
            self.refused = True
            await api_error_response(RequestTooLargeError.api_error)(
                self.scope, self._receive, self._send
            )


class BodyLimitMiddleware:
    """Refuse request bodies over a limit, larger on the upload paths."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_limit: int,
        upload_limit: int,
        upload_paths: Sequence[str],
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit
        self.upload_paths = tuple(upload_paths)

    def _is_upload(self, scope: Scope) -> bool:
        """Whether the request targets an upload path, or a resource under one."""
        if scope["method"] not in _UPLOAD_METHODS:
            return False
        path = scope["path"]
        return any(path == p or path.startswith(f"{p}/") for p in self.upload_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.upload_limit if self._is_upload(scope) else self.default_limit
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await api_error_response(RequestTooLargeError.api_error)(
                scope, receive, send
            )
            return
        guard = _Guard(scope, receive, send, limit)
        await self.app(scope, guard.receive, guard.send)
