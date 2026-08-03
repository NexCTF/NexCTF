"""Tests for normalised free-text labels (challenge category/tags, team bracket)."""

from httpx import AsyncClient

from nexctf.model import User
from nexctf.util.pydantic import normalise_label

CHALLENGE = "/admin/challenge/standard"


class TestNormaliseLabel:
    def test_collapses_case_and_whitespace(self) -> None:
        assert normalise_label("  Reverse   Engineering ") == "reverse engineering"
        assert normalise_label("WEB") == "web"

    def test_blank_becomes_none(self) -> None:
        assert normalise_label("   ") is None
        assert normalise_label("") is None
        assert normalise_label(None) is None


class TestChallengeLabels:
    async def test_category_and_tags_are_normalised(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(
            CHALLENGE,
            json={
                "title": "labelled",
                "category": "  Reverse   Engineering ",
                "tags": ["Easy", " easy ", "WEB"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["category"] == "reverse engineering"
        assert data["tags"] == ["easy", "web"]

    async def test_blank_category_is_null(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post(CHALLENGE, json={"title": "blank", "category": "  "})
        assert resp.status_code == 200
        assert resp.json()["data"]["category"] is None

    async def test_differently_cased_input_lands_on_one_facet_value(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        for title, category in (("a", "Web"), ("b", "web"), ("c", " WEB ")):
            resp = await c.post(
                CHALLENGE, json={"title": title, "category": category, "tags": ["Easy"]}
            )
            assert resp.status_code == 200

        resp = await c.get("/admin/challenge", params={"items_per_page": 1})
        assert resp.status_code == 200
        facets = resp.json()["filter_attributes"]
        assert facets["category"] == ["web"]
        assert facets["tags"] == ["easy"]


class TestTeamBracketLabels:
    async def test_bracket_is_normalised(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post("/admin/team", json={"name": "t1", "bracket": " Student "})
        assert resp.status_code == 200
        assert resp.json()["data"]["bracket"] == "student"

    async def test_bracket_facet_dedups_casing(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        for name, bracket in (("t1", "Student"), ("t2", "student")):
            resp = await c.post("/admin/team", json={"name": name, "bracket": bracket})
            assert resp.status_code == 200

        resp = await c.get("/admin/team", params={"items_per_page": 1})
        assert resp.status_code == 200
        assert resp.json()["filter_attributes"]["bracket"] == ["student"]


class TestLabelQueryParams:
    async def test_scoreboard_bracket_param_is_normalised(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        resp = await c.post("/admin/team", json={"name": "t1", "bracket": "student"})
        assert resp.status_code == 200

        resp = await c.get("/admin/scoreboard", params={"bracket": " Student "})
        assert resp.status_code == 200
        assert [e["team_name"] for e in resp.json()["data"]["entries"]] == ["t1"]
