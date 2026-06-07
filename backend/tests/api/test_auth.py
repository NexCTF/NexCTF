"""Tests for the auth endpoints: register, token login/logout, /me/tokens, TOTP, and OAuth."""

import hashlib
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from httpx import AsyncClient
import nexctf.core.appconfig as appconfig
import nexctf.crud as crud
from nexctf.api.security import hash_password, verify_password
from nexctf.exceptions import CaptchaInvalidError, CaptchaRequiredError
from nexctf.model import OAuthAccount, OAuthProvider, User, UserToken
from nexctf.schema import UserCreate
from nexctf.schema.user import AdminUserUpdate

from ..base import NULL_UUID


class TestRegister:
    async def test_register_success(self, http_client):
        resp = await http_client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "password": "strongpass",
                "email": "new@test.com",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["data"]["username"] == "newuser"
        assert data["data"]["email"] == "new@test.com"
        assert data["data"]["is_active"] is True
        assert data["data"]["role"] == "user"

    async def test_register_without_email(self, http_client):
        resp = await http_client.post(
            "/auth/register",
            json={"username": "noumail", "password": "strongpass"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["email"] is None

    async def test_register_duplicate_username(self, http_client):
        payload = {"username": "dupuser", "password": "pass123"}
        resp1 = await http_client.post("/auth/register", json=payload)
        assert resp1.status_code == 201
        resp2 = await http_client.post("/auth/register", json=payload)
        assert resp2.status_code == 409

    async def test_register_missing_fields(self, http_client):
        resp = await http_client.post(
            "/auth/register",
            json={"username": "incomplete"},
        )
        assert resp.status_code == 422

    async def test_register_disabled(self, http_client, monkeypatch):
        monkeypatch.setitem(appconfig._CACHE, "ctf.allow_registration", "false")
        resp = await http_client.post(
            "/auth/register",
            json={"username": "newuser", "password": "strongpass"},
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "AUTH-403-REG-DISABLED"

    async def test_register_captcha_required(self, http_client):
        with patch(
            "nexctf.api.routes.auth.verify_captcha",
            new_callable=AsyncMock,
            side_effect=CaptchaRequiredError,
        ):
            resp = await http_client.post(
                "/auth/register",
                json={"username": "newuser", "password": "strongpass"},
            )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "AUTH-CAPTCHA-REQUIRED"

    async def test_register_captcha_invalid(self, http_client):
        with patch(
            "nexctf.api.routes.auth.verify_captcha",
            new_callable=AsyncMock,
            side_effect=CaptchaInvalidError,
        ):
            resp = await http_client.post(
                "/auth/register",
                json={
                    "username": "newuser",
                    "password": "strongpass",
                    "cap_token": "bad",
                },
            )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "AUTH-CAPTCHA-INVALID"

    async def test_register_then_login(self, http_client, override_db_context):
        """Registered user can immediately log in."""
        resp = await http_client.post(
            "/auth/register",
            json={"username": "freshuser", "password": "mypassword"},
        )
        assert resp.status_code == 201

        login_resp = await http_client.post(
            "/auth/token",
            data={"username": "freshuser", "password": "mypassword"},
        )
        assert login_resp.status_code == 204
        assert "NexCTF" in login_resp.cookies

    async def test_register_disabled_check_before_captcha(
        self, http_client, monkeypatch
    ):
        """Registration-disabled 403 is returned before captcha is even checked."""
        monkeypatch.setitem(appconfig._CACHE, "ctf.allow_registration", "false")
        with patch(
            "nexctf.api.routes.auth.verify_captcha",
            new_callable=AsyncMock,
        ) as mock_captcha:
            resp = await http_client.post(
                "/auth/register",
                json={"username": "newuser", "password": "strongpass"},
            )
        assert resp.status_code == 403
        mock_captcha.assert_not_called()


class TestLogin:
    async def test_login_success(self, http_client, db_session):
        await crud.UserCrud.create(
            session=db_session,
            obj=UserCreate(
                username="logintest",
                hashed_password=hash_password("correct"),
            ),
        )
        await db_session.flush()

        resp = await http_client.post(
            "/auth/token",
            data={"username": "logintest", "password": "correct"},
        )
        assert resp.status_code == 204
        assert "NexCTF" in resp.cookies

    async def test_login_wrong_password(self, http_client, db_session):
        await crud.UserCrud.create(
            session=db_session,
            obj=UserCreate(
                username="wrongpw",
                hashed_password=hash_password("correct"),
            ),
        )
        await db_session.flush()

        resp = await http_client.post(
            "/auth/token",
            data={"username": "wrongpw", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, http_client):
        resp = await http_client.post(
            "/auth/token",
            data={"username": "nobody", "password": "anything"},
        )
        assert resp.status_code == 401

    async def test_login_inactive_user(self, http_client, db_session):
        user = await crud.UserCrud.create(
            session=db_session,
            obj=UserCreate(
                username="disabled",
                hashed_password=hash_password("pass"),
            ),
        )
        await db_session.flush()
        await crud.UserCrud.update(
            session=db_session,
            filters=[User.id == user.id],
            obj=AdminUserUpdate(id=user.id, is_active=False),
        )

        resp = await http_client.post(
            "/auth/token",
            data={"username": "disabled", "password": "pass"},
        )
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH-401"

    async def test_login_totp_required(self, http_client, db_session):
        secret = pyotp.random_base32()
        user = User(
            username="totp_user",
            hashed_password=hash_password("pass"),
            totp_secret=secret,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await http_client.post(
            "/auth/token",
            data={"username": "totp_user", "password": "pass"},
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "AUTH-TOTP-REQUIRED"

    async def test_login_invalid_totp(self, http_client, db_session):
        secret = pyotp.random_base32()
        user = User(
            username="totp_bad_code",
            hashed_password=hash_password("pass"),
            totp_secret=secret,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await http_client.post(
            "/auth/token",
            data={
                "username": "totp_bad_code",
                "password": "pass",
                "totp_code": "000000",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH-401-OTP"

    async def test_login_with_totp(self, http_client, db_session):
        secret = pyotp.random_base32()
        user = User(
            username="totp_ok",
            hashed_password=hash_password("pass"),
            totp_secret=secret,
        )
        db_session.add(user)
        await db_session.flush()

        code = pyotp.TOTP(secret).now()
        resp = await http_client.post(
            "/auth/token",
            data={"username": "totp_ok", "password": "pass", "totp_code": code},
        )
        assert resp.status_code == 204
        assert "NexCTF" in resp.cookies


class TestLogout:
    async def test_logout_unauthenticated(self, http_client):
        resp = await http_client.post("/auth/logout")
        assert resp.status_code == 204

    async def test_logout_clears_cookie(self, user_client):
        c, _ = user_client
        resp = await c.post("/auth/logout")
        assert resp.status_code == 204
        assert "NexCTF" not in c.cookies


class TestBearerAuth:
    async def test_bearer_token_authenticates(self, admin_client):
        c, _ = admin_client
        create_resp = await c.post("/me/tokens", json={"name": "bearer-test"})
        assert create_resp.status_code == 201
        raw_token = create_resp.json()["data"]["token"]

        resp = await c.get(
            "/me/tokens",
            headers={"Authorization": f"Bearer {raw_token}"},
            cookies={},
        )
        assert resp.status_code == 200

    async def test_invalid_bearer_token_rejected(
        self, http_client, override_db_context
    ):
        resp = await http_client.get(
            "/me/tokens",
            headers={"Authorization": "Bearer nexctf_invalidtoken"},
        )
        assert resp.status_code == 401

    async def test_bearer_wrong_prefix_rejected(self, http_client):
        resp = await http_client.get(
            "/me/tokens",
            headers={"Authorization": "Bearer wrongprefix_sometoken"},
        )
        assert resp.status_code == 401


class TestTokens:
    async def test_create_token(self, admin_client):
        c, _ = admin_client
        resp = await c.post(
            "/me/tokens",
            json={"name": "test-token"},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "test-token"
        assert data["token"] is not None
        assert data["expires_at"] is None

    async def test_list_tokens_empty(self, admin_client):
        c, _ = admin_client
        resp = await c.get("/me/tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total_count"] == 0
        assert data["data"] == []

    async def test_list_tokens_after_create(self, admin_client):
        c, _ = admin_client
        await c.post("/me/tokens", json={"name": "tok1"})
        resp = await c.get("/me/tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total_count"] == 1
        assert data["data"][0]["name"] == "tok1"
        # Token value should not be exposed in list
        assert data["data"][0]["token"] is None

    async def test_revoke_token(self, admin_client):
        c, _ = admin_client
        create_resp = await c.post("/me/tokens", json={"name": "revoke-me"})
        token_id = create_resp.json()["data"]["id"]

        resp = await c.delete(f"/me/tokens/{token_id}")
        assert resp.status_code == 204

        list_resp = await c.get("/me/tokens")
        assert list_resp.json()["pagination"]["total_count"] == 0

    async def test_revoke_nonexistent_token(self, admin_client):
        c, _ = admin_client
        resp = await c.delete(f"/me/tokens/{NULL_UUID}")
        assert resp.status_code == 404

    async def test_unauthorized_access(self, http_client):
        resp = await http_client.get("/me/tokens")
        assert resp.status_code in (307, 401)


class TestTotp:
    async def test_setup_totp(self, user_client):
        c, _ = user_client
        resp = await c.post("/me/totp/setup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "provisioning_uri" in data
        # secret no longer round-trips to the client
        assert "secret" not in data

    async def test_setup_totp_already_enabled(self, user_client, db_session):
        c, user = user_client
        secret = pyotp.random_base32()
        user.totp_secret = secret
        await db_session.flush()

        resp = await c.post("/me/totp/setup")
        assert resp.status_code == 409

    async def test_enable_totp(self, user_client, mock_redis):
        c, user = user_client
        secret = pyotp.random_base32()
        # Simulate the secret stored server-side by the setup endpoint
        mock_redis.get = AsyncMock(return_value=secret.encode())
        code = pyotp.TOTP(secret).now()

        resp = await c.post("/me/totp/enable", json={"code": code})
        assert resp.status_code == 204

    async def test_enable_totp_invalid_code(self, user_client, mock_redis):
        c, _ = user_client
        secret = pyotp.random_base32()
        mock_redis.get = AsyncMock(return_value=secret.encode())

        resp = await c.post("/me/totp/enable", json={"code": "000000"})
        assert resp.status_code == 401

    async def test_enable_totp_no_setup(self, user_client, mock_redis):
        c, _ = user_client
        mock_redis.get = AsyncMock(return_value=None)

        resp = await c.post("/me/totp/enable", json={"code": "123456"})
        assert resp.status_code == 401

    async def test_enable_totp_already_enabled(self, user_client, db_session):
        c, user = user_client
        secret = pyotp.random_base32()
        user.totp_secret = secret
        await db_session.flush()

        resp = await c.post("/me/totp/enable", json={"code": pyotp.TOTP(secret).now()})
        assert resp.status_code == 409

    async def test_disable_totp(self, user_client, db_session):
        c, user = user_client
        secret = pyotp.random_base32()
        user.totp_secret = secret
        await db_session.flush()

        code = pyotp.TOTP(secret).now()
        resp = await c.post("/me/totp/disable", json={"code": code})
        assert resp.status_code == 204

    async def test_disable_totp_invalid_code(self, user_client, db_session):
        c, user = user_client
        secret = pyotp.random_base32()
        user.totp_secret = secret
        await db_session.flush()

        resp = await c.post("/me/totp/disable", json={"code": "000000"})
        assert resp.status_code == 401

    async def test_disable_totp_not_enabled(self, user_client):
        c, _ = user_client
        resp = await c.post("/me/totp/disable", json={"code": "123456"})
        assert resp.status_code == 409

    async def test_totp_required_on_auth(self, user_client, mock_redis):
        """Cookie session remains valid even after TOTP is enabled (re-login is not forced)."""
        c, user = user_client
        secret = pyotp.random_base32()
        # Simulate the server-side secret stored by setup
        mock_redis.get = AsyncMock(return_value=secret.encode())
        code = pyotp.TOTP(secret).now()
        await c.post("/me/totp/enable", json={"code": code})

        resp = await c.get("/me/tokens")
        assert resp.status_code == 200


class TestPasswordReset:
    async def test_invalid_token(self, http_client, mock_redis) -> None:
        mock_redis.getdel = AsyncMock(return_value=None)
        resp = await http_client.post(
            "/auth/reset-password",
            json={"token": "bad_token", "new_password": "newpass"},
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "AUTH-400-RESET-TOKEN"

    async def test_reset_updates_password(
        self, http_client, db_session, mock_redis, override_db_context
    ) -> None:
        user = User(username="resetpw", hashed_password=hash_password("oldpass"))
        db_session.add(user)
        await db_session.flush()

        token = "test_reset_token_abc"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        mock_redis.getdel = AsyncMock(return_value=str(user.id))

        resp = await http_client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "newpass123"},
        )
        assert resp.status_code == 204

        mock_redis.getdel.assert_called_once_with(f"pwd_reset:{token_hash}")

        await db_session.refresh(user)
        assert user.hashed_password is not None
        assert verify_password("newpass123", user.hashed_password)

    async def test_reset_invalidates_api_tokens(
        self, http_client, db_session, mock_redis
    ) -> None:
        user = User(username="hastoken", hashed_password=hash_password("pass"))
        db_session.add(user)
        await db_session.flush()

        api_token = UserToken(user_id=user.id, token_hash="fakehash123")
        db_session.add(api_token)
        await db_session.flush()

        mock_redis.getdel = AsyncMock(return_value=str(user.id))

        resp = await http_client.post(
            "/auth/reset-password",
            json={"token": "any_token", "new_password": "newpass"},
        )
        assert resp.status_code == 204

        result = await crud.UserTokenCrud.first(
            session=db_session, filters=[UserToken.user_id == user.id]
        )
        assert result is None

    async def test_reset_is_single_use(
        self, http_client, db_session, mock_redis
    ) -> None:
        user = User(username="singleuse", hashed_password=hash_password("pass"))
        db_session.add(user)
        await db_session.flush()

        token = "single_use_token"

        # First call returns user_id, second returns None (token consumed atomically)
        mock_redis.getdel = AsyncMock(side_effect=[str(user.id), None])

        resp1 = await http_client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "pass1"},
        )
        assert resp1.status_code == 204

        resp2 = await http_client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "pass2"},
        )
        assert resp2.status_code == 400


class TestOAuthFlow:
    @pytest.fixture
    async def oauth_provider(self, db_session):
        provider = OAuthProvider(
            slug="test-idp",
            name="Test IdP",
            client_id="client-id",
            client_secret="client-secret",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
            scopes="openid email profile",
            is_active=True,
        )
        db_session.add(provider)
        await db_session.flush()
        return provider

    @pytest.fixture
    async def inactive_provider(self, db_session):
        provider = OAuthProvider(
            slug="inactive-idp",
            name="Inactive IdP",
            client_id="x",
            client_secret="x",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
            is_active=False,
        )
        db_session.add(provider)
        await db_session.flush()
        return provider

    _FAKE_URLS = (
        "https://idp.example.com/auth",
        "https://idp.example.com/token",
        "https://idp.example.com/userinfo",
    )

    async def test_authorize_redirects_to_provider(self, http_client, oauth_provider):
        with patch(
            "nexctf.api.routes.auth.oauth_resolve_provider_urls",
            new_callable=AsyncMock,
            return_value=self._FAKE_URLS,
        ):
            resp = await http_client.get(
                "/auth/providers/test-idp/authorize",
                follow_redirects=False,
            )

        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert location.startswith("https://idp.example.com/auth")
        assert "state=" in location
        assert "oauth_state_test-idp" in resp.headers.get("set-cookie", "")

    async def test_authorize_inactive_provider(self, http_client, inactive_provider):
        resp = await http_client.get(
            "/auth/providers/inactive-idp/authorize",
            follow_redirects=False,
        )
        assert resp.status_code == 404

    async def test_authorize_unknown_provider(self, http_client):
        resp = await http_client.get(
            "/auth/providers/does-not-exist/authorize",
            follow_redirects=False,
        )
        assert resp.status_code == 404

    async def test_callback_creates_new_user(self, http_client, oauth_provider):
        with patch(
            "nexctf.api.routes.auth.oauth_resolve_provider_urls",
            new_callable=AsyncMock,
            return_value=self._FAKE_URLS,
        ):
            auth_resp = await http_client.get(
                "/auth/providers/test-idp/authorize",
                follow_redirects=False,
            )

        assert auth_resp.status_code in (302, 307)
        state = parse_qs(urlparse(auth_resp.headers["location"]).query).get(
            "state", [None]
        )[0]

        with (
            patch(
                "nexctf.api.routes.auth.oauth_resolve_provider_urls",
                new_callable=AsyncMock,
                return_value=self._FAKE_URLS,
            ),
            patch(
                "nexctf.api.routes.auth.oauth_fetch_userinfo",
                new_callable=AsyncMock,
                return_value={"sub": "external-user-001", "email": "ext@example.com"},
            ),
        ):
            callback_resp = await http_client.get(
                "/auth/providers/test-idp/callback",
                params={"code": "authcode123", "state": state},
                follow_redirects=False,
            )

        assert callback_resp.status_code == 302
        assert "NexCTF" in callback_resp.cookies

    async def test_callback_logs_in_existing_oauth_account(
        self, http_client, db_session, oauth_provider, override_db_context
    ):
        # First login creates the account
        with patch(
            "nexctf.api.routes.auth.oauth_resolve_provider_urls",
            new_callable=AsyncMock,
            return_value=self._FAKE_URLS,
        ):
            auth_resp = await http_client.get(
                "/auth/providers/test-idp/authorize",
                follow_redirects=False,
            )
        state = parse_qs(urlparse(auth_resp.headers["location"]).query).get(
            "state", [None]
        )[0]

        with (
            patch(
                "nexctf.api.routes.auth.oauth_resolve_provider_urls",
                new_callable=AsyncMock,
                return_value=self._FAKE_URLS,
            ),
            patch(
                "nexctf.api.routes.auth.oauth_fetch_userinfo",
                new_callable=AsyncMock,
                return_value={"sub": "returning-user-001"},
            ),
        ):
            await http_client.get(
                "/auth/providers/test-idp/callback",
                params={"code": "code1", "state": state},
                follow_redirects=False,
            )

        # Second login with same sub uses the existing account — need a fresh state cookie
        with patch(
            "nexctf.api.routes.auth.oauth_resolve_provider_urls",
            new_callable=AsyncMock,
            return_value=self._FAKE_URLS,
        ):
            auth_resp2 = await http_client.get(
                "/auth/providers/test-idp/authorize",
                follow_redirects=False,
            )
        state2 = parse_qs(urlparse(auth_resp2.headers["location"]).query).get(
            "state", [None]
        )[0]

        with (
            patch(
                "nexctf.api.routes.auth.oauth_resolve_provider_urls",
                new_callable=AsyncMock,
                return_value=self._FAKE_URLS,
            ),
            patch(
                "nexctf.api.routes.auth.oauth_fetch_userinfo",
                new_callable=AsyncMock,
                return_value={"sub": "returning-user-001"},
            ),
        ):
            callback_resp = await http_client.get(
                "/auth/providers/test-idp/callback",
                params={"code": "code2", "state": state2},
                follow_redirects=False,
            )

        assert callback_resp.status_code == 302
        assert "NexCTF" in callback_resp.cookies

    async def test_callback_no_csrf_cookie_is_rejected(
        self, http_client, oauth_provider
    ):
        # Call callback without first going through /authorize (no CSRF cookie).
        # Previously this silently authenticated the user; now it must reject.
        resp = await http_client.get(
            "/auth/providers/test-idp/callback",
            params={"code": "code", "state": "tampered_state"},
            follow_redirects=False,
        )
        assert resp.status_code == 401

    async def test_callback_no_state_param_is_rejected(
        self, http_client, oauth_provider
    ):
        resp = await http_client.get(
            "/auth/providers/test-idp/callback",
            params={"code": "code"},
            follow_redirects=False,
        )
        assert resp.status_code == 401

    async def test_callback_inactive_provider(self, http_client, inactive_provider):
        resp = await http_client.get(
            "/auth/providers/inactive-idp/callback",
            params={"code": "x", "state": "x"},
            follow_redirects=False,
        )
        assert resp.status_code == 404

    async def test_callback_missing_sub_raises_error(self, http_client, oauth_provider):
        with patch(
            "nexctf.api.routes.auth.oauth_resolve_provider_urls",
            new_callable=AsyncMock,
            return_value=self._FAKE_URLS,
        ):
            auth_resp = await http_client.get(
                "/auth/providers/test-idp/authorize",
                follow_redirects=False,
            )
        state = parse_qs(urlparse(auth_resp.headers["location"]).query).get(
            "state", [None]
        )[0]

        with (
            patch(
                "nexctf.api.routes.auth.oauth_resolve_provider_urls",
                new_callable=AsyncMock,
                return_value=self._FAKE_URLS,
            ),
            patch(
                "nexctf.api.routes.auth.oauth_fetch_userinfo",
                new_callable=AsyncMock,
                return_value={"email": "no-sub@example.com"},
            ),
        ):
            resp = await http_client.get(
                "/auth/providers/test-idp/callback",
                params={"code": "code", "state": state},
                follow_redirects=False,
            )

        assert resp.status_code != 302


class TestSessionVersionInvalidation:
    """Verify that cookie sessions are invalidated after a password reset."""

    async def test_old_cookie_rejected_after_password_reset(
        self,
        client_factory,
        db_session,
        mock_redis,
        override_db_context,
    ) -> None:
        user = User(
            username="session_reset_user", hashed_password=hash_password("pass")
        )
        db_session.add(user)
        await db_session.flush()

        async with client_factory() as c:
            login_resp = await c.post(
                "/auth/token",
                data={"username": "session_reset_user", "password": "pass"},
            )
            assert login_resp.status_code == 204
            # Cookie is now bound to session_version=0
            assert "NexCTF" in c.cookies

            # Simulate a password reset that increments session_version
            mock_redis.getdel = AsyncMock(return_value=str(user.id))
            reset_resp = await c.post(
                "/auth/reset-password",
                json={"token": "any_reset_token", "new_password": "newpass"},
            )
            assert reset_resp.status_code == 204

            # The old cookie (version=0) must now be rejected
            me_resp = await c.get("/me/tokens")
            assert me_resp.status_code == 401


class TestLoginRateLimit:
    """Verify that the login endpoint enforces the per-IP rate limit."""

    async def test_login_returns_429_when_rate_limited(
        self, http_client, mock_redis
    ) -> None:
        # Make the sliding-window counter appear above the threshold (>10)
        mock_redis.pipeline.return_value.execute = AsyncMock(
            return_value=[None, None, 11, None]
        )
        resp = await http_client.post(
            "/auth/token",
            data={"username": "anyone", "password": "anypass"},
        )
        assert resp.status_code == 429

    async def test_password_reset_returns_429_when_rate_limited(
        self, http_client, mock_redis
    ) -> None:
        mock_redis.pipeline.return_value.execute = AsyncMock(
            return_value=[None, None, 6, None]
        )
        resp = await http_client.post(
            "/auth/reset-password",
            json={"token": "tok", "new_password": "newpass"},
        )
        assert resp.status_code == 429


class TestTokenOwnership:
    """Verify that API tokens can only be revoked by their owner."""

    async def test_cannot_revoke_another_users_token(
        self, client_factory, db_session, override_db_context
    ) -> None:
        # Create two users and log each in
        user_a = User(username="owner_a", hashed_password=hash_password("pass"))
        user_b = User(username="owner_b", hashed_password=hash_password("pass"))
        db_session.add_all([user_a, user_b])
        await db_session.flush()

        async with client_factory() as c_a, client_factory() as c_b:
            await c_a.post(
                "/auth/token", data={"username": "owner_a", "password": "pass"}
            )
            await c_b.post(
                "/auth/token", data={"username": "owner_b", "password": "pass"}
            )

            # User A creates a token
            create_resp = await c_a.post("/me/tokens", json={"name": "a-token"})
            assert create_resp.status_code == 201
            token_id = create_resp.json()["data"]["id"]

            # User B tries to revoke User A's token → 404 (not found under B's user_id)
            revoke_resp = await c_b.delete(f"/me/tokens/{token_id}")
            assert revoke_resp.status_code == 404

            # User A can still see and revoke their own token
            list_resp = await c_a.get("/me/tokens")
            assert list_resp.json()["pagination"]["total_count"] == 1


class TestBearerTokenExpiry:
    """Verify that expired bearer tokens are rejected."""

    async def test_expired_token_is_rejected(
        self, http_client, db_session, override_db_context
    ) -> None:
        from datetime import datetime, timedelta, timezone

        user = User(username="expiry_user", hashed_password=hash_password("pass"))
        db_session.add(user)
        await db_session.flush()

        expired_token = UserToken(
            user_id=user.id,
            token_hash=hashlib.sha256(b"nexctf_expiredtoken").hexdigest(),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(expired_token)
        await db_session.flush()

        resp = await http_client.get(
            "/me/tokens",
            headers={"Authorization": "Bearer nexctf_expiredtoken"},
        )
        assert resp.status_code == 401


class TestOAuthLinking:
    """Verify OAuth account linking behaviour introduced in fix/security."""

    @pytest.fixture
    async def oauth_provider(self, db_session):
        provider = OAuthProvider(
            slug="link-idp",
            name="Link IdP",
            client_id="client-id",
            client_secret="secret",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
            scopes="openid",
            is_active=True,
        )
        db_session.add(provider)
        await db_session.flush()
        return provider

    _FAKE_URLS = (
        "https://idp.example.com/auth",
        "https://idp.example.com/token",
        "https://idp.example.com/userinfo",
    )

    async def _do_authorize(self, client, slug="link-idp"):
        """Go through /authorize and return the state value."""
        from urllib.parse import parse_qs, urlparse

        with patch(
            "nexctf.api.routes.auth.oauth_resolve_provider_urls",
            new_callable=AsyncMock,
            return_value=self._FAKE_URLS,
        ):
            auth_resp = await client.get(
                f"/auth/providers/{slug}/authorize",
                follow_redirects=False,
            )
        assert auth_resp.status_code in (302, 307)
        state = parse_qs(urlparse(auth_resp.headers["location"]).query).get(
            "state", [None]
        )[0]
        return state

    async def test_email_in_userinfo_does_not_link_existing_account(
        self, client_factory, db_session, override_db_context, oauth_provider
    ) -> None:
        """An OAuth provider returning an email that matches an existing local account
        must NOT silently take over that account — a new account is created instead."""
        existing = User(
            username="local_user",
            email="shared@example.com",
            hashed_password=hash_password("pass"),
        )
        db_session.add(existing)
        await db_session.flush()

        async with client_factory() as c:
            state = await self._do_authorize(c)

            with (
                patch(
                    "nexctf.api.routes.auth.oauth_resolve_provider_urls",
                    new_callable=AsyncMock,
                    return_value=self._FAKE_URLS,
                ),
                patch(
                    "nexctf.api.routes.auth.oauth_fetch_userinfo",
                    new_callable=AsyncMock,
                    return_value={
                        "sub": "oauth-attacker-sub",
                        "email": "shared@example.com",
                    },
                ),
            ):
                callback_resp = await c.get(
                    "/auth/providers/link-idp/callback",
                    params={"code": "code", "state": state},
                    follow_redirects=False,
                )

            assert callback_resp.status_code == 302

        # The OAuth account must be linked to a *new* user, not the existing one.
        # The new account is created without the conflicting email.
        from nexctf.model import OAuthAccount

        oauth_acct = await crud.OAuthAccountCrud.first(
            session=db_session,
            filters=[OAuthAccount.subject == "oauth-attacker-sub"],
        )
        assert oauth_acct is not None
        assert oauth_acct.user_id != existing.id

        new_user = await crud.UserCrud.first(
            session=db_session, filters=[User.id == oauth_acct.user_id]
        )
        assert new_user is not None
        assert new_user.email is None  # conflicting email was not assigned

    async def test_oauth_links_to_logged_in_session(
        self, client_factory, db_session, override_db_context, oauth_provider
    ) -> None:
        """When a user is already logged in and completes an OAuth callback for a
        new (sub, provider) pair, the OAuthAccount is linked to their existing user."""
        user = User(username="already_logged_in", hashed_password=hash_password("pass"))
        db_session.add(user)
        await db_session.flush()

        async with client_factory() as c:
            login = await c.post(
                "/auth/token",
                data={"username": "already_logged_in", "password": "pass"},
            )
            assert login.status_code == 204

            state = await self._do_authorize(c)

            with (
                patch(
                    "nexctf.api.routes.auth.oauth_resolve_provider_urls",
                    new_callable=AsyncMock,
                    return_value=self._FAKE_URLS,
                ),
                patch(
                    "nexctf.api.routes.auth.oauth_fetch_userinfo",
                    new_callable=AsyncMock,
                    return_value={"sub": "new-oauth-sub-for-existing-user"},
                ),
            ):
                callback_resp = await c.get(
                    "/auth/providers/link-idp/callback",
                    params={"code": "code", "state": state},
                    follow_redirects=False,
                )

            assert callback_resp.status_code == 302

        from nexctf.model import OAuthAccount

        oauth_acct = await crud.OAuthAccountCrud.first(
            session=db_session,
            filters=[OAuthAccount.subject == "new-oauth-sub-for-existing-user"],
        )
        assert oauth_acct is not None
        assert oauth_acct.user_id == user.id

    async def test_oauth_callback_rejects_link_when_subject_belongs_to_different_user(
        self, client_factory, db_session, override_db_context, oauth_provider
    ) -> None:
        """If the OAuth subject is already linked to user B and user A is logged in,
        the callback must reject with 409 rather than silently switching to user B's
        session (which would be an implicit account takeover)."""
        from nexctf.model import OAuthAccount as OAuthAccountModel

        # user_b owns the OAuth account
        user_b = User(username="owner_b", hashed_password=hash_password("pass"))
        db_session.add(user_b)
        await db_session.flush()
        db_session.add(
            OAuthAccountModel(
                user_id=user_b.id,
                provider_id=oauth_provider.id,
                subject="shared-sub-conflict",
            )
        )

        # user_a is logged in
        user_a = User(username="logged_in_a", hashed_password=hash_password("pass"))
        db_session.add(user_a)
        await db_session.flush()

        async with client_factory() as c:
            await c.post(
                "/auth/token",
                data={"username": "logged_in_a", "password": "pass"},
            )

            state = await self._do_authorize(c)

            with (
                patch(
                    "nexctf.api.routes.auth.oauth_resolve_provider_urls",
                    new_callable=AsyncMock,
                    return_value=self._FAKE_URLS,
                ),
                patch(
                    "nexctf.api.routes.auth.oauth_fetch_userinfo",
                    new_callable=AsyncMock,
                    return_value={"sub": "shared-sub-conflict"},
                ),
            ):
                callback_resp = await c.get(
                    "/auth/providers/link-idp/callback",
                    params={"code": "code", "state": state},
                    follow_redirects=False,
                )

            assert callback_resp.status_code == 409
            assert callback_resp.json()["error_code"] == "OAUTH-409-ALREADY-LINKED"


class TestMeOAuth:
    """Tests for GET /me/oauth (list) and DELETE /me/oauth/{id} (unlink)."""

    @pytest.fixture
    async def linked_account(self, db_session, user_client, fixture_oauth_provider):
        """Link the test user to the test provider."""
        _, user = user_client
        provider = fixture_oauth_provider[0]
        account = OAuthAccount(
            user_id=user.id,
            provider_id=provider.id,
            subject="test-subject-me-oauth",
        )
        db_session.add(account)
        await db_session.flush()
        return account

    async def test_list_empty(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.get("/me/oauth")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_list_returns_linked_accounts(
        self,
        user_client: tuple[AsyncClient, User],
        linked_account: OAuthAccount,
    ) -> None:
        c, _ = user_client
        resp = await c.get("/me/oauth")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(linked_account.id)
        assert data[0]["provider_slug"] == "test-idp"

    async def test_unlink_success(
        self,
        user_client: tuple[AsyncClient, User],
        linked_account: OAuthAccount,
        mock_redis,
    ) -> None:
        c, _ = user_client
        resp = await c.delete(f"/me/oauth/{linked_account.id}")
        assert resp.status_code == 204

        resp2 = await c.get("/me/oauth")
        assert resp2.json()["data"] == []

    async def test_unlink_not_found(
        self, user_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = user_client
        resp = await c.delete(f"/me/oauth/{NULL_UUID}")
        assert resp.status_code == 404

    async def test_cannot_unlink_last_provider_without_password(
        self,
        client_factory,
        db_session,
        override_db_context,
        fixture_oauth_provider,
    ) -> None:
        """User with no password cannot unlink their only OAuth provider (→ 409)."""
        provider = fixture_oauth_provider[0]

        # Create user with a password so login works, then null it to simulate
        # a password-less account (e.g. OAuth-only user).
        user = User(username="no_pass_oauth_user", hashed_password=hash_password("tmp"))
        db_session.add(user)
        await db_session.flush()

        account = OAuthAccount(
            user_id=user.id,
            provider_id=provider.id,
            subject="no-pass-subject",
        )
        db_session.add(account)
        await db_session.flush()

        async with client_factory() as c:
            resp = await c.post(
                "/auth/token",
                data={"username": "no_pass_oauth_user", "password": "tmp"},
            )
            assert resp.status_code == 204

            # Simulate a passwordless account by removing the hash post-login.
            # The session cookie remains valid; next request re-reads user from DB.
            user.hashed_password = None
            await db_session.flush()

            resp = await c.delete(f"/me/oauth/{account.id}")
            assert resp.status_code == 409
            assert resp.json()["error_code"] == "OAUTH-409-LAST"
