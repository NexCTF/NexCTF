"""Shared permission-guard mixins for admin CRUD test classes.

Each mixin requires the subclass to define a ``PREFIX: str`` class variable.
Auth is checked before request-body validation, so minimal/empty payloads
are sufficient to trigger a 403 without needing a valid body.
"""

from httpx import AsyncClient

from nexctf.model import User

NULL_UUID = "00000000-0000-0000-0000-000000000000"


class ListGuardMixin:
    PREFIX: str

    async def test_requires_auth(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(self.PREFIX)
        assert resp.status_code in (307, 401)

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.get(self.PREFIX)
        assert resp.status_code == 403


class CreateGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.post(self.PREFIX, json={})
        assert resp.status_code == 403


class GetItemGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.get(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 403


class UpdateGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.put(f"{self.PREFIX}/{NULL_UUID}", json={"id": NULL_UUID})
        assert resp.status_code == 403


class DeleteGuardMixin:
    PREFIX: str

    async def test_requires_admin(self, user_client: tuple[AsyncClient, User]) -> None:
        c, _ = user_client
        resp = await c.delete(f"{self.PREFIX}/{NULL_UUID}")
        assert resp.status_code == 403
