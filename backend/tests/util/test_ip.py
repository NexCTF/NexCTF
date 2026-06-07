"""Unit tests for nexctf.util.ip.get_client_ip."""

from unittest.mock import MagicMock, patch

from starlette.datastructures import Headers

from nexctf.util.ip import get_client_ip


def _request(xff: str | None = None, client_host: str | None = "1.2.3.4") -> MagicMock:
    req = MagicMock()
    headers: dict[str, str] = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    req.headers = Headers(headers=headers)
    if client_host is not None:
        req.client = MagicMock(host=client_host)
    else:
        req.client = None
    return req


def test_xff_single_ip():
    assert get_client_ip(_request(xff="10.0.0.1")) == "10.0.0.1"


def test_xff_single_proxy_reads_rightmost():
    """With one trusted proxy the rightmost XFF entry is returned.

    The rightmost entry was appended by our trusted proxy (e.g. nginx); the
    leftmost entries are client-supplied and spoofable.
    """
    assert (
        get_client_ip(_request(xff="10.0.0.1, 172.16.0.1, 192.168.1.1"))
        == "192.168.1.1"
    )


def test_xff_strips_whitespace():
    assert get_client_ip(_request(xff="  10.0.0.2  , 10.0.0.3")) == "10.0.0.3"


def test_no_xff_falls_back_to_client_host():
    assert get_client_ip(_request(xff=None, client_host="9.9.9.9")) == "9.9.9.9"


def test_no_xff_no_client_returns_none():
    assert get_client_ip(_request(xff=None, client_host=None)) is None


def test_xff_multi_proxy_reads_nth_from_right():
    """With TRUSTED_PROXY_COUNT=2 the second entry from the right is returned."""
    import nexctf.util.ip as ip_module

    with patch.object(ip_module.settings, "TRUSTED_PROXY_COUNT", 2):
        assert (
            get_client_ip(_request(xff="10.0.0.1, 172.16.0.1, 192.168.1.1"))
            == "172.16.0.1"
        )


def test_xff_proxy_count_exceeds_chain_clamps_to_leftmost():
    """When fewer hops are present than TRUSTED_PROXY_COUNT, return the leftmost entry."""
    import nexctf.util.ip as ip_module

    with patch.object(ip_module.settings, "TRUSTED_PROXY_COUNT", 5):
        assert get_client_ip(_request(xff="10.0.0.1, 192.168.1.1")) == "10.0.0.1"


def test_trusted_proxy_count_zero_ignores_xff():
    """With TRUSTED_PROXY_COUNT=0 the XFF header is not trusted; the direct
    connection address is used regardless of what XFF says."""
    import nexctf.util.ip as ip_module

    with patch.object(ip_module.settings, "TRUSTED_PROXY_COUNT", 0):
        assert (
            get_client_ip(_request(xff="1.1.1.1", client_host="9.9.9.9")) == "9.9.9.9"
        )
        assert get_client_ip(_request(xff=None, client_host="9.9.9.9")) == "9.9.9.9"
