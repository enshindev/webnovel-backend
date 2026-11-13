from __future__ import annotations

from typing import Any
from uuid import UUID

from webnovel.modules.outbox.contract import OutboxEvent, OutboxService
from webnovel.modules.outbox.repository import OutboxRepository


class OutboxServiceImpl(OutboxService):
    def __init__(self, repository: OutboxRepository) -> None:
        self._repository = repository

    async def emit(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        return await self._repository.emit(aggregate_type, aggregate_id, event_type, payload)
