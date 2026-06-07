from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4


class FakeOrchestrator:
    """In-memory fake for testing the frontend plugin pipeline end-to-end."""

    def __init__(self) -> None:
        self._instances: dict[tuple[str, str], dict] = {}

    def _key(self, team_id: UUID, orchestrator_id: UUID) -> tuple[str, str]:
        return (str(team_id), str(orchestrator_id))

    def status(self, team_id: UUID, orchestrator_id: UUID) -> dict:
        return self._instances.get(self._key(team_id, orchestrator_id), {})

    def start(self, team_id: UUID, orchestrator_id: UUID) -> dict:
        key = self._key(team_id, orchestrator_id)
        now = datetime.now(UTC)
        instance = {
            "id": str(uuid4()),
            "challenge_id": str(orchestrator_id),
            "status": "running",
            "start_date": now.isoformat(),
            "stop_date": (now + timedelta(hours=2)).isoformat(),
            "urls": ["https://fake-ctf.example.com:8080"],
        }
        self._instances[key] = instance
        return instance

    def stop(self, team_id: UUID, orchestrator_id: UUID) -> dict:
        key = self._key(team_id, orchestrator_id)
        instance = self._instances.pop(key, {})
        if instance:
            instance["status"] = "stopped"
        return instance

    def renew(self, team_id: UUID, orchestrator_id: UUID) -> dict:
        key = self._key(team_id, orchestrator_id)
        if key in self._instances:
            now = datetime.now(UTC)
            self._instances[key]["stop_date"] = (now + timedelta(hours=2)).isoformat()
        return self._instances.get(key, {})
