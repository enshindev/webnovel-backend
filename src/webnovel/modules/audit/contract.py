from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AuditEntry:
    id: int
    ts: datetime
    actor: str
    action: str
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    prev_hash: str | None = None
    hash: str = ""


class AuditRecorder(Protocol):
    async def record(
        self,
        action: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry: ...


class AuditService(AuditRecorder, Protocol):
    async def list(self, limit: int = 100) -> list[AuditEntry]: ...
