"""Tests for the OAuth2 authorization server endpoints (/oauth2/*)."""

import json
from unittest.mock import AsyncMock

from httpx import AsyncClient

from nexctf.model import User
from nexctf.model.oauth_server import OAuthServerClient

_CLIENT_ID = "nexctf_testclientid"
_CLIENT_SECRET = "test_secret"
_REDIRECT_URI = "https://app.example.com/callback"

# RFC 7636 Appendix B reference S256 verifier/challenge pair
_PKCE_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
_PKCE_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

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


class TestOAuthServerMetadata:
    async def test_metadata_returns_required_fields(
        self, http_client: AsyncClient
    ) -> None:
        resp = await http_client.get("/oauth2/.well-known/oauth-authorization-server")
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

    async def test_approve_encodes_state_in_redirect(
        self,
        user_client: tuple[AsyncClient, User],
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        # A state with '&'/'#'/space must be percent-encoded so it cannot
        # inject extra params or a fragment into the redirect querystring.
        c, _ = user_client
        mock_redis.setex = AsyncMock(return_value=True)

        resp = await c.post(
            "/oauth2/authorize/approve",
            json={
                "client_id": _CLIENT_ID,
                "redirect_uri": _REDIRECT_URI,
                "scope": "openid profile",
                "state": "a b&evil=1#frag",
            },
        )
        assert resp.status_code == 200
        redirect_to = resp.json()["data"]["redirect_to"]
        assert "state=a%20b%26evil%3D1%23frag" in redirect_to
        assert "&evil=1" not in redirect_to

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


class TestOAuth2PKCE:
    """PKCE (RFC 7636) is optional but strictly verified when a challenge is bound."""

    _CODE_PAYLOAD_PKCE = json.dumps(
        {
            "client_id": _CLIENT_ID,
            "user_id": "00000000-0000-4000-8001-000000000002",  # fx_user1
            "redirect_uri": _REDIRECT_URI,
            "scopes": "openid profile email",
            "state": None,
            "code_challenge": _PKCE_CHALLENGE,
        }
    )

    async def test_discovery_advertises_s256(self, http_client: AsyncClient) -> None:
        resp = await http_client.get("/oauth2/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        assert "S256" in resp.json()["code_challenge_methods_supported"]

    async def test_authorize_carries_challenge_to_consent(
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
                "code_challenge": _PKCE_CHALLENGE,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f"code_challenge={_PKCE_CHALLENGE}" in resp.headers["location"]

    async def test_authorize_rejects_non_s256_method(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
    ) -> None:
        # 'plain' is deprecated by OAuth 2.1 and not supported by this server
        resp = await http_client.get(
            "/oauth2/authorize",
            params={
                "client_id": _CLIENT_ID,
                "redirect_uri": _REDIRECT_URI,
                "response_type": "code",
                "code_challenge": _PKCE_CHALLENGE,
                "code_challenge_method": "plain",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_approve_binds_challenge_into_code(
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
                "code_challenge": _PKCE_CHALLENGE,
                "code_challenge_method": "S256",
            },
        )
        assert resp.status_code == 200
        stored_payload = json.loads(mock_redis.setex.call_args.args[2])
        assert stored_payload["code_challenge"] == _PKCE_CHALLENGE

    async def test_approve_rejects_non_s256_method(
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
                "redirect_uri": _REDIRECT_URI,
                "scope": "openid profile",
                "code_challenge": _PKCE_CHALLENGE,
                "code_challenge_method": "plain",
            },
        )
        assert resp.status_code == 400

    async def test_token_with_valid_verifier(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
        fixture_user_members,
        mock_redis,
    ) -> None:
        mock_redis.get = AsyncMock(return_value=self._CODE_PAYLOAD_PKCE)
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
                "code_verifier": _PKCE_VERIFIER,
            },
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_token_missing_verifier_when_bound(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        # A challenge was bound at authorization, so omitting the verifier must fail
        mock_redis.get = AsyncMock(return_value=self._CODE_PAYLOAD_PKCE)
        mock_redis.delete = AsyncMock()

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
        assert resp.status_code == 400

    async def test_token_wrong_verifier(
        self,
        http_client: AsyncClient,
        fixture_oauth_server_client: list[OAuthServerClient],
        mock_redis,
    ) -> None:
        mock_redis.get = AsyncMock(return_value=self._CODE_PAYLOAD_PKCE)
        mock_redis.delete = AsyncMock()

        resp = await http_client.post(
            "/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": "test_code_value",
                "redirect_uri": _REDIRECT_URI,
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "code_verifier": "wrong_verifier_padded_to_min_length_xxxxxxx",
            },
        )
        assert resp.status_code == 400
        # The code must be consumed even on a failed PKCE check (no retry).
        mock_redis.delete.assert_called_once()


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
