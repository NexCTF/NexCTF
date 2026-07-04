"""Test-only fixtures"""

import hashlib
from uuid import UUID

from fastapi_toolsets.fixtures import FixtureRegistry

from nexctf.model import ChallengeCategory, OAuthProvider, Tag, Team, User, UserRole
from nexctf.model.oauth_server import OAuthServerClient

fixtures = FixtureRegistry()


@fixtures.register()
def team() -> list[Team]:
    return [
        Team(
            id=UUID("00000000-0000-4000-8000-000000000100"),
            name="alpha",
        ),
    ]


@fixtures.register()
def user_admin() -> list[User]:
    return [
        User(
            id=UUID("00000000-0000-4000-8001-000000000001"),
            username="fx_admin",
            hashed_password="x",
            role=UserRole.admin,
        ),
    ]


@fixtures.register(depends_on=["team"])
def user_members() -> list[User]:
    alpha_id = fixtures.field("team", "name", "alpha")
    return [
        User(
            id=UUID("00000000-0000-4000-8001-000000000002"),
            username="fx_user1",
            hashed_password="x",
            team_id=alpha_id,
        ),
        User(
            id=UUID("00000000-0000-4000-8001-000000000003"),
            username="fx_user2",
            hashed_password="x",
            team_id=alpha_id,
        ),
    ]


@fixtures.register()
def user_moderator() -> list[User]:
    return [
        User(
            id=UUID("00000000-0000-4000-8001-000000000004"),
            username="fx_moderator",
            hashed_password="x",
            role=UserRole.moderator,
        ),
    ]


@fixtures.register()
def user_with_totp() -> list[User]:
    return [
        User(
            id=UUID("00000000-0000-4000-8002-000000000001"),
            username="fx_totp_user",
            hashed_password="x",
            totp_secret="JBSWY3DPEHPK3PXP",
        ),
    ]


@fixtures.register()
def tag() -> list[Tag]:
    return [
        Tag(
            id=UUID("00000000-0000-4000-8003-000000000001"),
            name="Hard",
            description="",
            color="#e01b24",
        ),
        Tag(
            id=UUID("00000000-0000-4000-8003-000000000002"),
            name="Easy",
            description="",
            color="#33d17a",
        ),
    ]


@fixtures.register()
def challenge_category() -> list[ChallengeCategory]:
    return [
        ChallengeCategory(
            id=UUID("00000000-0000-4000-8004-000000000001"),
            slug="web",
            name="Web",
        ),
        ChallengeCategory(
            id=UUID("00000000-0000-4000-8004-000000000002"),
            slug="re",
            name="Reverse Engineering",
        ),
    ]


@fixtures.register()
def oauth_provider() -> list[OAuthProvider]:
    return [
        OAuthProvider(
            id=UUID("00000000-0000-4000-8005-000000000001"),
            slug="test-idp",
            name="Test IdP",
            client_id="test-client-id",
            client_secret="test-client-secret",
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
            scopes="openid email profile",
            is_active=True,
        ),
    ]


@fixtures.register()
def oauth_server_client() -> list[OAuthServerClient]:
    return [
        OAuthServerClient(
            id=UUID("00000000-0000-4000-8006-000000000001"),
            name="Test App",
            client_id="nexctf_testclientid",
            client_secret_hash=hashlib.sha256(b"test_secret").hexdigest(),
            redirect_uris="https://app.example.com/callback",
            allowed_scopes="openid profile email roles",
            is_active=True,
        ),
        OAuthServerClient(
            id=UUID("00000000-0000-4000-8006-000000000002"),
            name="Admin App",
            client_id="nexctf_adminonly",
            client_secret_hash=hashlib.sha256(b"test_secret").hexdigest(),
            redirect_uris="https://app.example.com/callback",
            allowed_scopes="openid profile email roles",
            allowed_roles="admin",
            is_active=True,
        ),
    ]
