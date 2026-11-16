"""Same-origin check for the browser-facing routes that accept anonymous posts.

Mirrors the CSRF rules of fastapi_multiauth's cookie source
(``APIKeyCookieAuth._check_origin``), which only guards signed-in requests and
exposes no public helper; keep the two in step.
"""

from fastapi import Request

from nexctf.core.config import settings
from nexctf.exceptions import CrossOriginRequestError

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_TRUSTED_ORIGINS = frozenset(settings.all_cors_origins)


def _matches_host(request: Request, origin: str) -> bool:
    """Whether *origin* is the host the request was sent to."""
    host = request.headers.get("host", "").lower()
    schemes = ("https",) if settings.secure_cookies else ("https", "http")
    return bool(host) and origin in {f"{scheme}://{host}" for scheme in schemes}


async def require_same_origin(request: Request) -> None:
    """Refuse a write another site made a browser send, as login CSRF does.

    A request carrying neither ``Sec-Fetch-Site`` nor ``Origin`` did not come
    from a browser and is let through.
    """
    if request.method in _SAFE_METHODS:
        return
    site = request.headers.get("sec-fetch-site")
    origin = request.headers.get("origin")
    if site is None and origin is None:
        return
    if site in ("same-origin", "none"):
        return
    if origin is not None:
        origin = origin.lower()
        if origin in _TRUSTED_ORIGINS:
            return
        if site is None and _matches_host(request, origin):
            return
    raise CrossOriginRequestError()
