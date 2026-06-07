from __future__ import annotations

import asyncio
from uuid import UUID

from redis.asyncio import Redis


async def publish_notification(
    redis: Redis,
    is_broadcast: bool,
    team_ids: list[UUID],
    notif_json: str,
) -> None:
    publishes = []
    if is_broadcast:
        publishes.append(redis.publish("notifications:broadcast", notif_json))
    for team_id in team_ids:
        publishes.append(redis.publish(f"notifications:team:{team_id}", notif_json))
    if publishes:
        await asyncio.gather(*publishes)
