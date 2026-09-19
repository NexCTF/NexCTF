"""The /admin/bundle endpoints: guards, export, plan review and apply."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.scope import _token_scopes, set_token_scopes
from nexctf.bundle.archive import write_archive
from nexctf.bundle.tree import write_tree
from nexctf.core import s3
from nexctf.core.appconfig import ConfigType, all_defs
from nexctf.model import ConfigEntry, CustomPage, User
from nexctf.module import bundle
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge

from ..base import ListGuardMixin

PREFIX = "/admin/bundle"


def _a_secret_key() -> str:
    return next(
        key for key, def_ in all_defs().items() if def_.type is ConfigType.SECRET
    )


def _config_of(archive: bytes) -> dict[str, str]:
    """The config section an exported archive carries."""
    return bundle.parse_archive(archive)[0].config


def _with_config(archive: bytes, overrides: dict[str, str]) -> bytes:
    """The same archive, with *overrides* applied to its config section."""
    incoming, blobs = bundle.parse_archive(archive)
    incoming.config.update(overrides)
    return write_archive(write_tree(incoming, blobs))


@pytest.fixture
async def page(db_session: AsyncSession) -> CustomPage:
    page = CustomPage(slug="rules", title="Rules", content="# Rules")
    db_session.add(page)
    await db_session.flush()
    return page


@pytest.fixture
async def exported(admin_client: tuple[AsyncClient, User], page: CustomPage) -> bytes:
    """The archive the export endpoint hands back."""
    c, _ = admin_client
    resp = await c.get(f"{PREFIX}/export")
    assert resp.status_code == 200
    return resp.content


class TestExportGuards(ListGuardMixin):
    PREFIX = f"{PREFIX}/export"


class TestExport:
    async def test_the_export_is_the_archive_itself(self, exported: bytes) -> None:
        assert exported[:2] == b"PK"
        assert "nexctf.yaml" in bundle.read_archive(exported)

    async def test_the_download_is_named_after_the_moment_it_was_built(
        self, admin_client: tuple[AsyncClient, User], page: CustomPage
    ) -> None:
        c, _ = admin_client
        resp = await c.get(f"{PREFIX}/export")
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith('attachment; filename="nexctf-bundle-')
        assert resp.headers["content-type"] == "application/zip"

    async def test_nothing_is_kept_in_storage(
        self, admin_client: tuple[AsyncClient, User], page: CustomPage
    ) -> None:
        c, _ = admin_client
        await c.get(f"{PREFIX}/export")
        assert await s3.list_prefix("exports/") == []

    async def test_secrets_stay_behind_by_default(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        secret = _a_secret_key()
        db_session.add(ConfigEntry(key=secret, value="hunter2"))
        await db_session.flush()

        resp = await c.get(f"{PREFIX}/export")

        assert b"hunter2" not in resp.content
        assert secret not in _config_of(resp.content)

    async def test_secrets_travel_when_the_caller_asks(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        secret = _a_secret_key()
        db_session.add(ConfigEntry(key=secret, value="hunter2"))
        await db_session.flush()

        resp = await c.get(f"{PREFIX}/export", params={"include_secrets": "true"})

        assert _config_of(resp.content)[secret] == "hunter2"

    async def test_files_can_be_left_out(
        self, admin_client: tuple[AsyncClient, User], page: CustomPage
    ) -> None:
        c, _ = admin_client
        resp = await c.get(f"{PREFIX}/export", params={"include_files": "false"})
        assert resp.status_code == 200
        assert "nexctf.yaml" in bundle.read_archive(resp.content)


class TestImportPlan:
    async def test_re_importing_an_export_plans_no_writes(
        self, admin_client: tuple[AsyncClient, User], exported: bytes
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            f"{PREFIX}/import/plan", files={"upload": ("bundle.zip", exported)}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data["counts"]) == {"unchanged"}
        assert data["import_key"].startswith(bundle.IMPORT_PREFIX)
        await s3.delete(data["import_key"])

    async def test_a_plan_writes_nothing(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        exported: bytes,
        page: CustomPage,
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            f"{PREFIX}/import/plan", files={"upload": ("bundle.zip", exported)}
        )
        await s3.delete(resp.json()["data"]["import_key"])

        await db_session.refresh(page)
        assert page.title == "Rules"

    async def test_a_secret_value_never_reaches_the_plan_response(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        page: CustomPage,
    ) -> None:
        """The plan is reviewed in a browser, so it must carry no secret value."""
        c, _ = admin_client
        secret = _a_secret_key()
        db_session.add(ConfigEntry(key=secret, value="stored-password"))
        await db_session.flush()

        exported = (
            await c.get(f"{PREFIX}/export", params={"include_secrets": "true"})
        ).content
        edited = _with_config(exported, {secret: "incoming-password"})

        resp = await c.post(
            f"{PREFIX}/import/plan", files={"upload": ("bundle.zip", edited)}
        )

        assert resp.status_code == 200
        assert b"stored-password" not in resp.content
        assert b"incoming-password" not in resp.content
        entry = next(e for e in resp.json()["data"]["entries"] if e["id"] == secret)
        assert entry["changes"][secret] == ["***", "***"]
        await s3.delete(resp.json()["data"]["import_key"])

    async def test_a_non_archive_answers_400(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            f"{PREFIX}/import/plan", files={"upload": ("x.zip", b"not a zip")}
        )
        assert resp.status_code == 400

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.post(f"{PREFIX}/import/plan", files={"upload": ("x.zip", b"x")})
        assert resp.status_code == 403


class TestImportApply:
    async def test_an_edited_bundle_applies_through_the_api(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        exported: bytes,
        page: CustomPage,
    ) -> None:
        c, _ = admin_client
        page.title = "Stale"
        await db_session.flush()

        plan = (
            await c.post(
                f"{PREFIX}/import/plan", files={"upload": ("bundle.zip", exported)}
            )
        ).json()["data"]
        assert plan["counts"].get("update") == 1

        resp = await c.post(
            f"{PREFIX}/import/apply", json={"import_key": plan["import_key"]}
        )
        assert resp.status_code == 200
        await db_session.refresh(page)
        assert page.title == "Rules"

    async def test_an_unknown_staged_key_answers_400(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            f"{PREFIX}/import/apply",
            json={"import_key": f"{bundle.IMPORT_PREFIX}{uuid4()}.zip"},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("key", ["imports/../exports/x.zip", "files/x.zip"])
    async def test_a_key_outside_the_import_prefix_answers_400(
        self, admin_client: tuple[AsyncClient, User], key: str
    ) -> None:
        c, _ = admin_client
        resp = await c.post(f"{PREFIX}/import/apply", json={"import_key": key})
        assert resp.status_code == 400

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.post(f"{PREFIX}/import/apply", json={"import_key": "x"})
        assert resp.status_code == 403


class TestExportScope:
    """The payload carries flags, so the router group alone cannot gate it."""

    async def test_a_bundle_only_token_cannot_export(
        self, db_session: AsyncSession
    ) -> None:
        from nexctf.api.routes.admin.bundle import _require_challenge_read
        from nexctf.exceptions import InsufficientScopeError

        token = _token_scopes.set(None)
        try:
            set_token_scopes(["read:admin.bundle", "write:admin.bundle"])
            with pytest.raises(InsufficientScopeError):
                _require_challenge_read()
        finally:
            _token_scopes.reset(token)

    async def test_a_session_is_not_scope_checked(self) -> None:
        from nexctf.api.routes.admin.bundle import _require_challenge_read

        token = _token_scopes.set(None)
        try:
            _require_challenge_read()
        finally:
            _token_scopes.reset(token)


class TestApplyPreservesIds:
    async def test_a_created_challenge_keeps_the_bundle_id(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        exported: bytes,
    ) -> None:
        c, _ = admin_client
        incoming, blobs = bundle.parse_archive(exported)
        from nexctf.bundle.ir import ChallengeIR

        challenge_id = uuid4()
        incoming.challenges.append(
            ChallengeIR(
                id=challenge_id, challenge_type="standard", title="Imported Challenge"
            )
        )
        edited = write_archive(write_tree(incoming, blobs))
        plan = (
            await c.post(
                f"{PREFIX}/import/plan", files={"upload": ("bundle.zip", edited)}
            )
        ).json()["data"]
        resp = await c.post(
            f"{PREFIX}/import/apply", json={"import_key": plan["import_key"]}
        )
        assert resp.status_code == 200
        assert await db_session.get(StandardChallenge, challenge_id) is not None
