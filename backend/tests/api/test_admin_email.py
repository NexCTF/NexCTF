"""Tests for the admin SMTP test-email endpoint."""

from unittest.mock import AsyncMock, patch

from nexctf.exceptions import (
    EmailDisabledError,
    EmailMisconfiguredError,
    EmailSendError,
)

TEST_EMAIL_PATH = "/admin/email/test"
PAYLOAD = {"to": "ops@example.com"}


def _patch_send():
    return patch("nexctf.api.routes.admin.email.send_email", new_callable=AsyncMock)


class TestSendTestEmail:
    async def test_requires_admin(self, user_client):
        """A regular user cannot trigger a test email."""
        client, _ = user_client
        resp = await client.post(TEST_EMAIL_PATH, json=PAYLOAD)
        assert resp.status_code == 403

    async def test_requires_auth(self, http_client):
        """An unauthenticated request is rejected."""
        resp = await http_client.post(TEST_EMAIL_PATH, json=PAYLOAD)
        assert resp.status_code in (401, 403)

    async def test_invalid_recipient_rejected(self, admin_client):
        """A malformed recipient never reaches the SMTP layer."""
        client, _ = admin_client
        with _patch_send() as mock_send:
            resp = await client.post(TEST_EMAIL_PATH, json={"to": "not-an-email"})
        assert resp.status_code == 422
        mock_send.assert_not_called()

    async def test_success(self, admin_client):
        """A configured send returns success and forwards the recipient."""
        client, _ = admin_client
        with _patch_send() as mock_send:
            resp = await client.post(TEST_EMAIL_PATH, json=PAYLOAD)
        assert resp.status_code == 200
        mock_send.assert_awaited_once()
        assert mock_send.await_args.args[1] == "ops@example.com"

    async def test_disabled_surfaces_409(self, admin_client):
        client, _ = admin_client
        with _patch_send() as mock_send:
            mock_send.side_effect = EmailDisabledError
            resp = await client.post(TEST_EMAIL_PATH, json=PAYLOAD)
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "EMAIL-409-DISABLED"

    async def test_misconfigured_surfaces_500(self, admin_client):
        client, _ = admin_client
        with _patch_send() as mock_send:
            mock_send.side_effect = EmailMisconfiguredError
            resp = await client.post(TEST_EMAIL_PATH, json=PAYLOAD)
        assert resp.status_code == 500
        assert resp.json()["error_code"] == "EMAIL-500"

    async def test_send_failure_surfaces_502(self, admin_client):
        client, _ = admin_client
        with _patch_send() as mock_send:
            mock_send.side_effect = EmailSendError
            resp = await client.post(TEST_EMAIL_PATH, json=PAYLOAD)
        assert resp.status_code == 502
        assert resp.json()["error_code"] == "EMAIL-502"
