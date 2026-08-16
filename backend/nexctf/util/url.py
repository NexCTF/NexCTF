"""URL construction helpers."""

from urllib.parse import quote, urlencode, urlsplit


def append_query(url: str, params: dict[str, str]) -> str:
    """Append *params* to *url*, preserving any query string it already carries."""
    sep = "&" if urlsplit(url).query else "?"
    return f"{url}{sep}{urlencode(params, quote_via=quote)}"
