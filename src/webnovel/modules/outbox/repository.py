from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.outbox.contract import OutboxEvent
from webnovel.modules.outbox.models import OutboxEventModel


class OutboxRepository(Protocol):
    async def emit(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEvent: ...


def _to_domain(model: OutboxEventModel) -> OutboxEvent:
    return OutboxEvent(
        id=model.id,
        aggregate_type=model.aggregate_type,
        aggregate_id=model.aggregate_id,
        event_type=model.event_type,
        payload=model.payload,
        status=model.status,
        attempts=model.attempts,
        available_at=model.available_at,
        created_at=model.created_at,
    )


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def emit(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        model = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)
