from typing import Any
from uuid import UUID

import httpx
from nexctf.plugins.config import get_plugin_config


class Orchestrator:
    def __init__(self):
        headers = httpx.Headers(
            {
                "Authorization": f"Bearer {get_plugin_config('instance_token')}",
                "Content-Type": "application/json",
            }
        )
        self.client = httpx.Client(
            headers=headers,
            base_url=f"{get_plugin_config('instance_url')}/api/v1",
            verify=bool(get_plugin_config("instance_verify")),
        )

    def _fetch_all(self, endpoint: str) -> list[dict[str, Any]]:
        all_data = []
        page = 0

        while True:
            response = self.client.get(url=endpoint, params={"page": page})
            response.raise_for_status()
            result = response.json()
            data = result.get("data", [])
            all_data.extend(data)
            if not result.get("has_more"):
                break
            page += 1

        return all_data

    def get_containers(self) -> list[dict[str, Any]]:
        return self._fetch_all(endpoint="/orchestrator")

    def start(self, team_id: UUID, orchestrator_id: UUID) -> dict[str, Any]:
        r = self.client.post(
            url="/instance/start",
            params=[
                ("team_id", str(team_id)),
                ("orchestrator_id", str(orchestrator_id)),
            ],
        )
        r.raise_for_status()
        return r.json()

    def stop(self, team_id: UUID, orchestrator_id: UUID) -> dict[str, Any]:
        r = self.client.post(
            url="/instance/stop",
            params=[
                ("team_id", str(team_id)),
                ("orchestrator_id", str(orchestrator_id)),
            ],
        )
        r.raise_for_status()
        return r.json()

    def status(self, team_id: UUID, orchestrator_id: UUID) -> dict[str, Any]:
        r = self.client.get(
            url="/instance/status",
            params=[
                ("team_id", str(team_id)),
                ("orchestrator_id", str(orchestrator_id)),
            ],
        )
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()

    def renew(self, team_id: UUID, orchestrator_id: UUID) -> dict[str, Any]:
        r = self.client.post(
            url="/instance/renew",
            params=[
                ("team_id", str(team_id)),
                ("orchestrator_id", str(orchestrator_id)),
            ],
        )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self.client.close()
