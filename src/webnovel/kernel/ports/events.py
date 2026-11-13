from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, object]


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
