"""Tests for the cookie credential validator in nexctf.api.security."""

import pytest
from fastapi_toolsets.exceptions import UnauthorizedError

from nexctf.api.security import _verify_cookie


class TestVerifyCookie:
    """A signed cookie whose payload is malformed is rejected, not a crash."""

    @pytest.mark.parametrize(
        "credential",
        [
            "not-a-uuid:1",  # user id does not parse
            "00000000-0000-4000-8001-000000000002:notanint",  # version does not parse
            "no-separator",  # does not split into two parts
        ],
    )
    async def test_malformed_payload_is_unauthorized(self, credential: str) -> None:
        with pytest.raises(UnauthorizedError):
            await _verify_cookie(credential)
