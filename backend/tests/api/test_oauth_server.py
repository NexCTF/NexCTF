"""Tests for the OAuth2 authorization server endpoints (/oauth2/*)."""

import json
from unittest.mock import AsyncMock

from httpx import AsyncClient

from nexctf.model import User
from nexctf.model.oauth_server import OAuthServerClient

_CLIENT_ID = "nexctf_testclientid"
_CLIENT_SECRET = "test_secret"
_REDIRECT_URI = "https://app.example.com/callback"

# Shared code payload used across token-related tests
_CODE_PAYLOAD = json.dumps(
    {
        "client_id": _CLIENT_ID,
        "user_id": "00000000-0000-4000-8001-000000000002",  # fx_user1 UUID
        "redirect_uri": _REDIRECT_URI,
        "scopes": "openid profile email",
        "state": None,
    }
)


class TestOIDCDiscovery:
    async def test_discovery_returns_required_fields(
        self, http_client: AsyncClient
    ) -> None:
        resp = await http_client.get("/oauth2/.well-known/openid-configuration")
        assert resp.status_code == 200
        data = resp.json()
        assert "issuer" in data
        assert "authorization_endpoint" in data
        assert "token_endpoint" in data
        assert "userinfo_endpoint" in data
        assert "code" in data["response_types_supported"]
        assert "authorization_code" in data["grant_types_supported"]


class TestOAuth2Authorize:
    async def test_redirects_to_consent_page(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        resp = await http_client.get(
            "/oauth2/authorize",
            params={
                "client_id": _CLIENT_ID,
                "redirect_uri": _REDIRECT_URI,
                "response_type": "code",
                "scope": "openid profile",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/oauth/consent" in resp.headers["location"]
        assert _CLIENT_ID in resp.headers["location"]

    async def test_invalid_client_id(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(
            "/oauth2/authorize",
            params={
                "client_id": "unknown_client",
                "redirect_uri": _REDIRECT_URI,
                "response_type": "code",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_invalid_redirect_uri(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        resp = await http_client.get(
            "/oauth2/authorize",
            params={
                "client_id": _CLIENT_ID,
                "redirect_uri": "https://evil.example.com/callback",
                "response_type": "code",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_unsupported_response_type(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        resp = await http_client.get(
            "/oauth2/authorize",
            params={
                "client_id": _CLIENT_ID,
                "redirect_uri": _REDIRECT_URI,
                "response_type": "token",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400


class TestOAuth2ClientInfo:
    async def test_returns_client_and_scope_info(
        self,
        user_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        c, user = user_client
        resp = await c.get(
            "/oauth2/client-info",
            params={"client_id": _CLIENT_ID, "scope": "openid profile"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["client_id"] == _CLIENT_ID
        assert data["client_name"] == "Test App"
        assert data["username"] == user.username
        assert "openid" in data["requested_scopes"]
        assert "profile" in data["requested_scopes"]

    async def test_unknown_scopes_filtered(
        self,
        user_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        c, _ = user_client
        resp = await c.get(
            "/oauth2/client-info",
            params={"client_id": _CLIENT_ID, "scope": "openid unknown_scope"},
        )
        assert resp.status_code == 200
        scopes = resp.json()["data"]["requested_scopes"]
        assert "openid" in scopes
        assert "unknown_scope" not in scopes

    async def test_invalid_client(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.get(
            "/oauth2/client-info",
            params={"client_id": "no_such_client"},
        )
        assert resp.status_code == 400

    async def test_requires_auth(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(
            "/oauth2/client-info",
            params={"client_id": _CLIENT_ID},
        )
        assert resp.status_code in (307, 401)


class TestOAuth2Approve:
    async def test_approve_returns_redirect_url(
        self,
        user_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        c, _ = user_client
        mock_redis.setex = AsyncMock(return_value=True)

        resp = await c.post(
            "/oauth2/authorize/approve",
            json={
                "client_id": _CLIENT_ID,
                "redirect_uri": _REDIRECT_URI,
                "scope": "openid profile",
            },
        )
        assert resp.status_code == 200
        redirect_to = resp.json()["data"]["redirect_to"]
        assert redirect_to.startswith(_REDIRECT_URI)
        assert "code=" in redirect_to
        mock_redis.setex.assert_called_once()

    async def test_approve_with_state(
        self,
        user_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        c, _ = user_client
        mock_redis.setex = AsyncMock(return_value=True)

        resp = await c.post(
            "/oauth2/authorize/approve",
            json={
                "client_id": _CLIENT_ID,
                "redirect_uri": _REDIRECT_URI,
                "scope": "openid profile",
                "state": "csrf_token_abc",
            },
        )
        assert resp.status_code == 200
        redirect_to = resp.json()["data"]["redirect_to"]
        assert "state=csrf_token_abc" in redirect_to

    async def test_approve_invalid_client(
        self, user_client: tuple[AsyncClient, User], mock_redis
    ) -> None:
        c, _ = user_client
        resp = await c.post(
            "/oauth2/authorize/approve",
            json={
                "client_id": "no_such_client",
                "redirect_uri": _REDIRECT_URI,
                "scope": "openid",
            },
        )
        assert resp.status_code == 400

    async def test_approve_invalid_redirect_uri(
        self,
        user_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        c, _ = user_client
        resp = await c.post(
            "/oauth2/authorize/approve",
            json={
                "client_id": _CLIENT_ID,
                "redirect_uri": "https://evil.example.com/callback",
                "scope": "openid",
            },
        )
        assert resp.status_code == 400

    async def test_approve_requires_auth(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        resp = await http_client.post(
            "/oauth2/authorize/approve",
            json={"client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI},
        )
        assert resp.status_code in (307, 401)


class TestOAuth2Token:
    async def test_exchange_code_for_token(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
        fixture_user_members,
        mock_redis,
    ) -> None:
        mock_redis.get = AsyncMock(return_value=_CODE_PAYLOAD)
        mock_redis.delete = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)

        resp = await http_client.post(
            "/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": "test_code_value",
                "redirect_uri": _REDIRECT_URI,
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        mock_redis.setex.assert_called_once()

    async def test_invalid_code(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        # Default mock_redis.get returns None — simulates expired/unknown code
        resp = await http_client.post(
            "/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": "bad_code",
                "redirect_uri": _REDIRECT_URI,
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
            },
        )
        assert resp.status_code == 400

    async def test_wrong_client_secret(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        resp = await http_client.post(
            "/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": "test_code_value",
                "redirect_uri": _REDIRECT_URI,
                "client_id": _CLIENT_ID,
                "client_secret": "wrong_secret",
            },
        )
        assert resp.status_code == 401

    async def test_unsupported_grant_type(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        resp = await http_client.post(
            "/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "code": "x",
                "redirect_uri": _REDIRECT_URI,
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
            },
        )
        assert resp.status_code == 400


class TestOAuth2Userinfo:
    _TOKEN_PAYLOAD = json.dumps(
        {
            "client_id": _CLIENT_ID,
            "user_id": "00000000-0000-4000-8001-000000000002",  # fx_user1
            "scopes": "openid profile email roles",
        }
    )

    async def test_returns_user_claims(
        self,
        http_client: AsyncClient,
        fixture_user_members,
        mock_redis,
    ) -> None:
        mock_redis.get = AsyncMock(return_value=self._TOKEN_PAYLOAD)

        resp = await http_client.get(
            "/oauth2/userinfo",
            headers={"Authorization": "Bearer some_opaque_token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sub" in data
        assert data["username"] == "fx_user1"
        assert data["role"] == "user"

    async def test_missing_bearer(self, http_client: AsyncClient) -> None:
        resp = await http_client.get("/oauth2/userinfo")
        assert resp.status_code == 401

    async def test_invalid_token(self, http_client: AsyncClient, mock_redis) -> None:
        # Default mock_redis.get returns None — simulates expired/unknown token
        resp = await http_client.get(
            "/oauth2/userinfo",
            headers={"Authorization": "Bearer expired_token"},
        )
        assert resp.status_code == 401

    async def test_scope_filtering_profile_only(
        self,
        http_client: AsyncClient,
        fixture_user_members,
        mock_redis,
    ) -> None:
        payload = json.dumps(
            {
                "client_id": _CLIENT_ID,
                "user_id": "00000000-0000-4000-8001-000000000002",
                "scopes": "openid profile",
            }
        )
        mock_redis.get = AsyncMock(return_value=payload)

        resp = await http_client.get(
            "/oauth2/userinfo",
            headers={"Authorization": "Bearer some_opaque_token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "fx_user1"
        assert data["email"] is None
        assert data["role"] is None
