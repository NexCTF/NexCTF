"""Unique-column writes must answer 409, never an unhandled IntegrityError."""

from httpx import AsyncClient

from nexctf.model import User


class TestCustomFieldConflicts:
    PREFIX = "/admin/custom-field"

    def _body(self, name: str) -> dict:
        return {"name": name, "label": "Label", "target": "user"}

    async def test_create_duplicate_key(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        assert (await c.post(self.PREFIX, json=self._body("dup"))).status_code == 200

        resp = await c.post(self.PREFIX, json=self._body("dup"))
        assert resp.status_code == 409

    async def test_update_duplicate_key(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        assert (await c.post(self.PREFIX, json=self._body("dup"))).status_code == 200
        other = await c.post(self.PREFIX, json=self._body("other"))
        other_id = other.json()["data"]["id"]

        resp = await c.put(
            f"{self.PREFIX}/{other_id}", json={"id": other_id, "name": "dup"}
        )
        assert resp.status_code == 409


class TestOAuthProviderConflicts:
    PREFIX = "/admin/oauth-provider"

    def _body(self, slug: str) -> dict:
        return {
            "slug": slug,
            "name": "Provider",
            "client_id": "cid",
            "client_secret": "secret",
            "discovery_url": "https://example.com/.well-known/openid-configuration",
        }

    async def test_create_duplicate_slug(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        assert (await c.post(self.PREFIX, json=self._body("dup"))).status_code == 200

        resp = await c.post(self.PREFIX, json=self._body("dup"))
        assert resp.status_code == 409

    async def test_update_duplicate_slug(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        assert (await c.post(self.PREFIX, json=self._body("dup"))).status_code == 200
        other = await c.post(self.PREFIX, json=self._body("other"))
        other_id = other.json()["data"]["id"]

        resp = await c.put(
            f"{self.PREFIX}/{other_id}", json={"id": other_id, "slug": "dup"}
        )
        assert resp.status_code == 409


class TestChallengeConflicts:
    PREFIX = "/admin/challenge"

    def _body(self, title: str) -> dict:
        return {"title": title, "description": "d", "category": "misc"}

    async def test_create_duplicate_title(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        create = f"{self.PREFIX}/standard"
        assert (await c.post(create, json=self._body("dup"))).status_code == 200

        resp = await c.post(create, json=self._body("dup"))
        assert resp.status_code == 409

    async def test_update_duplicate_title(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        create = f"{self.PREFIX}/standard"
        assert (await c.post(create, json=self._body("dup"))).status_code == 200
        other = await c.post(create, json=self._body("other"))
        other_id = other.json()["data"]["id"]

        resp = await c.put(
            f"{self.PREFIX}/{other_id}", json={"id": other_id, "title": "dup"}
        )
        assert resp.status_code == 409
