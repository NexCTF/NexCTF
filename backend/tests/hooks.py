"""Recorder for the admin lifecycle hooks of ``StandardChallenge``."""

from dataclasses import dataclass, field
from uuid import UUID

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge


@dataclass
class HookCall:
    """One hook call: its name, the challenge id, ``obj`` and ``changed``."""

    name: str
    challenge_id: UUID
    obj: BaseModel | None = None
    changed: set[str] | None = None


@dataclass
class HookRecorder:
    """Records every admin hook call; raises ``raise_with`` once set."""

    calls: list[HookCall] = field(default_factory=list)
    raise_with: Exception | None = None

    def record(self, call: HookCall) -> None:
        """Append ``call``, then raise ``raise_with`` if set."""
        self.calls.append(call)
        if self.raise_with is not None:
            raise self.raise_with


@pytest.fixture
def hooks(monkeypatch: pytest.MonkeyPatch) -> HookRecorder:
    """Patch StandardChallenge's admin hooks to record into a fresh recorder."""
    recorder = HookRecorder()

    async def after_create(
        self: StandardChallenge, session: AsyncSession, obj: BaseModel
    ) -> None:
        recorder.record(HookCall("after_create", self.id, obj))

    async def after_update(
        self: StandardChallenge,
        session: AsyncSession,
        obj: BaseModel,
        changed: set[str],
    ) -> None:
        recorder.record(HookCall("after_update", self.id, obj, changed))

    async def before_delete(self: StandardChallenge, session: AsyncSession) -> None:
        recorder.record(HookCall("before_delete", self.id))

    monkeypatch.setattr(StandardChallenge, "after_create", after_create)
    monkeypatch.setattr(StandardChallenge, "after_update", after_update)
    monkeypatch.setattr(StandardChallenge, "before_delete", before_delete)
    return recorder
