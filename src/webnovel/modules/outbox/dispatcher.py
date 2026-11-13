from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.infra.config import get_settings
from webnovel.modules.audit.contract import AuditRecorder
from webnovel.modules.outbox.models import OutboxEventModel

logger = structlog.get_logger(__name__)
Handler = Callable[[OutboxEventModel], Awaitable[None]]


async def dispatch_once(
    session: AsyncSession,
    limit: int = 50,
    audit: AuditRecorder | None = None,
    handler: Handler | None = None,
    *,
    max_attempts: int = 5,
    base_delay_seconds: int = 30,
) -> int:
    now = datetime.now(UTC)
    rows = (
        (
            await session.execute(
                select(OutboxEventModel)
                .where(
                    OutboxEventModel.status.in_(["pending", "retry"]),
                    or_(
                        OutboxEventModel.available_at.is_(None),
                        OutboxEventModel.available_at <= now,
                    ),
                )
                .order_by(OutboxEventModel.id.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    processed = 0
    for row in rows:
        try:
            await (handler or _handle)(row)
        except Exception as exc:
            row.attempts += 1
            row.last_error = str(exc)
            if row.attempts >= max_attempts:
                row.status = "dead"
                logger.exception("outbox.dead", event_id=row.id, attempts=row.attempts)
            else:
                row.status = "retry"
                delay = base_delay_seconds * (2 ** max(0, row.attempts - 1))
                row.next_attempt_at = now + timedelta(seconds=delay)
                row.available_at = row.next_attempt_at
                logger.warning(
                    "outbox.retry",
                    event_id=row.id,
                    attempts=row.attempts,
                    next_attempt_at=row.next_attempt_at.isoformat(),
                )
            continue
        if audit is not None:
            await audit.record(
                f"outbox.{row.event_type}",
                target_type=row.aggregate_type,
                target_id=str(row.aggregate_id),
                metadata={"event_id": row.id},
            )
        row.status = "done"
        row.processed_at = datetime.now(UTC)
        processed += 1
    await session.flush()
    return processed


async def _handle(event: OutboxEventModel) -> None:
    """默认 handler：可选推送到 webhook；未配置时保持 no-op。"""
    url = get_settings().outbox_webhook_url
    if not url:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            json={
                "event_id": event.id,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": str(event.aggregate_id),
                "event_type": event.event_type,
                "payload": event.payload,
            },
        )
        response.raise_for_status()
