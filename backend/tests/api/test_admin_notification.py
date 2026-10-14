"""Tests for the admin notification endpoints."""

import json
from unittest.mock import patch

from httpx import AsyncClient

from nexctf.model import User
from nexctf.schema.notification import PublicNotificationItem


class TestCreateNotification:
    async def test_announced_with_the_public_view(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, admin = admin_client
        published: list[dict] = []

        async def _publish(_redis, _channels, data: str) -> None:
            published.append(json.loads(data))

        with patch("nexctf.module.notification.publish_event", _publish):
            resp = await c.post(
                "/admin/notification",
                json={
                    "title": "Hi",
                    "content": "Body",
                    "is_broadcast": True,
                    "created_by_id": str(admin.id),
                },
            )

        assert resp.status_code == 200
        [payload] = published
        assert set(payload) == set(PublicNotificationItem.model_fields)
