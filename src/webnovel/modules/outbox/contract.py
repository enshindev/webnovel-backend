from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    id: int
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0
    available_at: datetime | None = None
    created_at: datetime | None = None


class OutboxService(Protocol):
    async def emit(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEvent: ...
