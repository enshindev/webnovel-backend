from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.audit.contract import AuditEntry
from webnovel.modules.audit.models import AuditLogModel


class AuditRepository(Protocol):
    async def append(
        self,
        action: str,
        *,
        target_type: str | None,
        target_id: str | None,
        metadata: dict[str, Any],
    ) -> AuditEntry: ...

    async def list(self, limit: int) -> list[AuditEntry]: ...


def _to_domain(model: AuditLogModel) -> AuditEntry:
    return AuditEntry(
        id=model.id,
        ts=model.ts,
        actor=model.actor,
        action=model.action,
        target_type=model.target_type,
        target_id=model.target_id,
        metadata=model.meta,
        prev_hash=model.prev_hash,
        hash=model.hash,
    )


class SqlAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        action: str,
        *,
        target_type: str | None,
        target_id: str | None,
        metadata: dict[str, Any],
    ) -> AuditEntry:
        last = (
            await self._session.execute(
                select(AuditLogModel).order_by(AuditLogModel.id.desc()).limit(1)
            )
        ).scalar_one_or_none()
        prev_hash = last.hash if last is not None else None
        payload = {
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": metadata,
            "prev_hash": prev_hash,
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        model = AuditLogModel(
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=metadata,
            prev_hash=prev_hash,
            hash=digest,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list(self, limit: int) -> list[AuditEntry]:
        rows = (
            (
                await self._session.execute(
                    select(AuditLogModel).order_by(AuditLogModel.id.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [_to_domain(row) for row in rows]
