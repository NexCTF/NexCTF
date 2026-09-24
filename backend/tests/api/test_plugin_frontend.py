"""Plugin bundles: public and admin manifests, and the files they point at."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from nexctf.model import User
from nexctf.plugins import FrontendDef, PageDef, loader
from nexctf.plugins.frontend import frontend_registry


@pytest.fixture
def demo_bundles(isolated_plugins: None, tmp_path: Path) -> Path:
    """Register a plugin with a public and an admin bundle, plus a stray file."""
    (tmp_path / "bundle.js").write_text("/* public */")
    (tmp_path / "admin.js").write_text("/* admin */")
    (tmp_path / "admin.css").write_text(".admin {}")
    (tmp_path / "chunk.js").write_text("/* not declared */")
    frontend_registry.add(
        FrontendDef(
            tmp_path,
            slots=["challenge_panel"],
            admin_entry_file="admin.js",
            admin_entry_css="admin.css",
            admin_slots=["admin_panel"],
            admin_pages=[PageDef("workers", {"en": "Workers"}, icon="server")],
        ),
        owner="demo",
    )
    return tmp_path


async def test_the_public_manifest_lists_only_the_public_bundle(
    http_client: AsyncClient, demo_bundles: Path
) -> None:
    resp = await http_client.get("/plugins/manifest")

    assert resp.status_code == 200
    (entry,) = resp.json()
    assert entry["remote_entry"].startswith(
        "/api/v1/plugins/demo/frontend/bundle.js?v="
    )
    assert entry["integrity"].startswith("sha384-")
    assert entry["slots"] == ["challenge_panel"]
    assert entry["stylesheet"] is None
    assert entry["pages"] == []


async def test_the_admin_manifest_lists_only_the_admin_bundle(
    admin_client: tuple[AsyncClient, User], demo_bundles: Path
) -> None:
    client, _ = admin_client
    resp = await client.get("/admin/plugins/manifest")

    assert resp.status_code == 200
    (entry,) = resp.json()
    assert entry["remote_entry"].startswith(
        "/api/v1/admin/plugins/demo/frontend/admin.js?v="
    )
    assert entry["slots"] == ["admin_panel"]
    assert entry["stylesheet"]["url"].startswith(
        "/api/v1/admin/plugins/demo/frontend/admin.css?v="
    )
    assert entry["stylesheet"]["integrity"].startswith("sha384-")
    assert entry["pages"] == [
        {
            "path": "workers",
            "label": {"en": "Workers"},
            "icon": "server",
            "section": "plugins",
        }
    ]


async def test_the_public_route_serves_only_the_public_entry(
    http_client: AsyncClient, demo_bundles: Path
) -> None:
    ok = await http_client.get("/plugins/demo/frontend/bundle.js")
    assert ok.status_code == 200
    assert ok.text == "/* public */"
    for name in ("admin.js", "chunk.js", "../bundle.js"):
        resp = await http_client.get(f"/plugins/demo/frontend/{name}")
        assert resp.status_code == 404, name


async def test_a_bundle_at_its_current_version_is_cached_for_good(
    http_client: AsyncClient, demo_bundles: Path
) -> None:
    (entry,) = (await http_client.get("/plugins/manifest")).json()
    url = entry["remote_entry"].removeprefix("/api/v1")

    current = await http_client.get(url)
    stale = await http_client.get("/plugins/demo/frontend/bundle.js?v=old")

    assert current.headers["cache-control"] == ("public, max-age=31536000, immutable")
    assert stale.headers["cache-control"] == "no-cache"


async def test_an_admin_bundle_is_only_cached_privately(
    admin_client: tuple[AsyncClient, User], demo_bundles: Path
) -> None:
    client, _ = admin_client
    (entry,) = (await client.get("/admin/plugins/manifest")).json()

    resp = await client.get(entry["remote_entry"].removeprefix("/api/v1"))

    assert resp.headers["cache-control"].startswith("private,")


async def test_a_player_cannot_fetch_admin_code(
    user_client: tuple[AsyncClient, User], demo_bundles: Path
) -> None:
    client, _ = user_client
    assert (await client.get("/admin/plugins/manifest")).status_code == 403
    assert (
        await client.get("/admin/plugins/demo/frontend/admin.js")
    ).status_code == 403


async def test_an_admin_fetches_the_admin_entry_only(
    admin_client: tuple[AsyncClient, User], demo_bundles: Path
) -> None:
    client, _ = admin_client
    ok = await client.get("/admin/plugins/demo/frontend/admin.js")
    assert ok.status_code == 200
    assert ok.text == "/* admin */"
    resp = await client.get("/admin/plugins/demo/frontend/bundle.js")
    assert resp.status_code == 404


async def test_the_plugin_list_reports_missing_bundles(
    admin_client: tuple[AsyncClient, User],
    isolated_plugins: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        loader, "_plugin_metadata", {"demo": loader._builtin_metadata("demo")}
    )
    frontend_registry.add(FrontendDef(tmp_path), owner="demo")
    client, _ = admin_client

    (plugin,) = (await client.get("/admin/plugins")).json()["data"]

    assert plugin["missing_bundles"] == ["bundle.js"]
    assert plugin["is_disabled"] is False
    assert plugin["has_config"] is False


async def test_an_admin_stylesheet_is_served_as_css_to_admins_only(
    admin_client: tuple[AsyncClient, User],
    http_client: AsyncClient,
    demo_bundles: Path,
) -> None:
    client, _ = admin_client
    (entry,) = (await client.get("/admin/plugins/manifest")).json()

    resp = await client.get(entry["stylesheet"]["url"].removeprefix("/api/v1"))

    assert resp.status_code == 200
    assert resp.text == ".admin {}"
    assert resp.headers["content-type"].startswith("text/css")
    assert resp.headers["cache-control"].startswith("private,")
    public = await http_client.get("/plugins/demo/frontend/admin.css")
    assert public.status_code == 404
