"""Tests for email verification (login gate) and password-reset initiation."""

import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from nexctf.api.security import hash_password
from nexctf.model import Event, User


def _enable_email(mock_redis) -> None:
    """Make the email.enabled config read (via get_with_overrides) resolve true."""
    mock_redis.hgetall = AsyncMock(return_value={"email.enabled": "true"})


async def _event_count(db_session, event_type: str) -> int:
    rows = await db_session.scalars(select(Event).where(Event.event_type == event_type))
    return len(rows.all())


def _patch_dispatch():
    """Replace the background email dispatcher so no real send is attempted."""
    return patch("nexctf.api.routes.auth.dispatch_email", new_callable=AsyncMock)


class TestRegisterVerification:
    async def test_email_enabled_creates_unverified_and_sends(
        self, http_client, db_session, mock_redis, override_db_context
    ):
        """With SMTP on, a registered email is unverified and gets a verify mail."""
        _enable_email(mock_redis)
        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/register",
                json={
                    "username": "needsverify",
                    "password": "strongpass",
                    "email": "nv@test.com",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["data"]["email_verified"] is False

        user = await db_session.scalar(
            select(User).where(User.username == "needsverify")
        )
        assert user.email_verified is False
        # A verification token was stored and a verification email scheduled.
        assert any(
            call.args[0].startswith("email_verify:")
            for call in mock_redis.setex.await_args_list
        )
        dispatch.assert_awaited_once()

    async def test_email_disabled_creates_verified_no_send(
        self, http_client, mock_redis
    ):
        """With SMTP off there is no way to verify, so the account is usable."""
        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/register",
                json={
                    "username": "noverify",
                    "password": "strongpass",
                    "email": "x@test.com",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["data"]["email_verified"] is True
        dispatch.assert_not_awaited()

    async def test_email_required_when_enabled(self, http_client, mock_redis):
        """With SMTP on, registering without an email is rejected."""
        _enable_email(mock_redis)
        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/register",
                json={"username": "noemail", "password": "strongpass"},
            )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "AUTH-400-EMAIL-REQUIRED"
        dispatch.assert_not_awaited()

    async def test_no_email_ok_when_disabled(self, http_client):
        """With SMTP off, email stays optional and the account is verified."""
        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/register",
                json={"username": "noemaildisabled", "password": "strongpass"},
            )
        assert resp.status_code == 201
        assert resp.json()["data"]["email_verified"] is True
        dispatch.assert_not_awaited()


class TestLoginGate:
    async def _make_user(self, db_session, *, email, verified):
        user = User(
            username="gateuser",
            email=email,
            hashed_password=hash_password("pass123"),
            email_verified=verified,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    async def test_unverified_blocked_when_email_enabled(
        self, http_client, db_session, mock_redis, override_db_context
    ):
        _enable_email(mock_redis)
        await self._make_user(db_session, email="gate@test.com", verified=False)
        resp = await http_client.post(
            "/auth/token", data={"username": "gateuser", "password": "pass123"}
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "AUTH-403-EMAIL-NOT-VERIFIED"

    async def test_unverified_allowed_when_email_disabled(
        self, http_client, db_session, override_db_context
    ):
        """SMTP off must not lock out users who could never verify."""
        await self._make_user(db_session, email="gate@test.com", verified=False)
        resp = await http_client.post(
            "/auth/token", data={"username": "gateuser", "password": "pass123"}
        )
        assert resp.status_code == 204

    async def test_verified_allowed(
        self, http_client, db_session, mock_redis, override_db_context
    ):
        _enable_email(mock_redis)
        await self._make_user(db_session, email="gate@test.com", verified=True)
        resp = await http_client.post(
            "/auth/token", data={"username": "gateuser", "password": "pass123"}
        )
        assert resp.status_code == 204

    async def test_no_email_allowed(
        self, http_client, db_session, mock_redis, override_db_context
    ):
        _enable_email(mock_redis)
        await self._make_user(db_session, email=None, verified=False)
        resp = await http_client.post(
            "/auth/token", data={"username": "gateuser", "password": "pass123"}
        )
        assert resp.status_code == 204


class TestVerifyEmail:
    async def test_valid_token_marks_verified(
        self, http_client, db_session, mock_redis, override_db_context
    ):
        user = User(
            username="toverify",
            email="tv@test.com",
            hashed_password=hash_password("pass"),
            email_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        token = "verify_token_xyz"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        mock_redis.getdel = AsyncMock(return_value=str(user.id))

        resp = await http_client.post("/auth/verify-email", json={"token": token})
        assert resp.status_code == 204
        mock_redis.getdel.assert_called_once_with(f"email_verify:{token_hash}")

        await db_session.refresh(user)
        assert user.email_verified is True
        # The action is audited.
        assert await _event_count(db_session, "user.email_verified") == 1

    async def test_invalid_token(self, http_client, mock_redis):
        mock_redis.getdel = AsyncMock(return_value=None)
        resp = await http_client.post("/auth/verify-email", json={"token": "bad"})
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "AUTH-400-VERIFY-TOKEN"


class TestForgotPassword:
    async def test_known_email_sends_reset(
        self, http_client, db_session, mock_redis, override_db_context
    ):
        _enable_email(mock_redis)
        user = User(
            username="forgetme",
            email="fp@test.com",
            hashed_password=hash_password("pass"),
            email_verified=True,
        )
        db_session.add(user)
        await db_session.flush()

        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/forgot-password", json={"email": "fp@test.com"}
            )
        assert resp.status_code == 204
        assert any(
            call.args[0].startswith("pwd_reset:")
            for call in mock_redis.setex.await_args_list
        )
        dispatch.assert_awaited_once()
        assert await _event_count(db_session, "user.password_reset_requested") == 1

    async def test_known_email_case_insensitive(
        self, http_client, db_session, mock_redis, override_db_context
    ):
        """A reset request must match regardless of the stored email's casing."""
        _enable_email(mock_redis)
        user = User(
            username="caseme",
            email="Case@Test.com",
            hashed_password=hash_password("pass"),
            email_verified=True,
        )
        db_session.add(user)
        await db_session.flush()

        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/forgot-password", json={"email": "case@test.com"}
            )
        assert resp.status_code == 204
        dispatch.assert_awaited_once()

    async def test_unknown_email_is_silent(self, http_client, mock_redis):
        """No account enumeration: unknown email still returns 204, sends nothing."""
        _enable_email(mock_redis)
        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/forgot-password", json={"email": "nobody@test.com"}
            )
        assert resp.status_code == 204
        dispatch.assert_not_awaited()
        assert not any(
            call.args[0].startswith("pwd_reset:")
            for call in mock_redis.setex.await_args_list
        )


class TestResendVerification:
    @pytest.mark.parametrize("verified", [False, True])
    async def test_resend_respects_verified_state(
        self, http_client, db_session, mock_redis, override_db_context, verified
    ):
        _enable_email(mock_redis)
        user = User(
            username="resendme",
            email="rs@test.com",
            hashed_password=hash_password("pass"),
            email_verified=verified,
        )
        db_session.add(user)
        await db_session.flush()

        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/resend-verification", json={"email": "rs@test.com"}
            )
        assert resp.status_code == 204
        # Already-verified users get nothing; unverified get a fresh mail + audit event.
        assert dispatch.await_count == (0 if verified else 1)
        assert await _event_count(db_session, "user.verification_resent") == (
            0 if verified else 1
        )

    async def test_resend_noop_when_email_disabled(
        self, http_client, db_session, override_db_context
    ):
        user = User(
            username="resenddisabled",
            email="rsd@test.com",
            hashed_password=hash_password("pass"),
            email_verified=False,
        )
        db_session.add(user)
        await db_session.flush()
        with _patch_dispatch() as dispatch:
            resp = await http_client.post(
                "/auth/resend-verification", json={"email": "rsd@test.com"}
            )
        assert resp.status_code == 204
        dispatch.assert_not_awaited()
