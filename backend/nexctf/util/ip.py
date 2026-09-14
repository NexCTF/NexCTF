"""Client IP extraction with configurable proxy trust."""

from __future__ import annotations

from fastapi import Request
from starlette.types import Scope

from nexctf.core.config import settings


def get_client_ip(request: Request) -> str | None:
    """Return the client's IP address, honouring TRUSTED_PROXY_COUNT."""
    return client_ip_from_scope(request.scope)


def client_ip_from_scope(scope: Scope) -> str | None:
    """Return the client's IP address for an ASGI scope, honouring TRUSTED_PROXY_COUNT.

    When TRUSTED_PROXY_COUNT is 0, the direct connection address is used
    and X-Forwarded-For is ignored entirely to prevent spoofing.

    When >= 1, the client IP is read N entries from the right of
    X-Forwarded-For, where N is TRUSTED_PROXY_COUNT. Each trusted proxy
    appends the address it received from, so the rightmost N entries are
    added by trusted infrastructure and the (N)-th from the right is the
    real client. Reading the leftmost entry would trust a value the client
    fully controls (proxies that append, e.g. nginx's
    ``$proxy_add_x_forwarded_for``, leave the client-supplied prefix intact),
    allowing IP spoofing.
    """
    client = scope.get("client")
    host = client[0] if client else None
    if settings.TRUSTED_PROXY_COUNT == 0:
        return host
    xff = next(
        (value for name, value in scope["headers"] if name == b"x-forwarded-for"),
        None,
    )
    if xff:
        parts = [p.strip() for p in xff.decode("latin-1").split(",") if p.strip()]
        if parts:
            # Clamp to the available entries: if fewer hops than configured
            # are present, fall back to the leftmost (most-trusted) entry
            # rather than indexing out of range.
            index = min(settings.TRUSTED_PROXY_COUNT, len(parts))
            return parts[-index]
    return host
