from __future__ import annotations

from typing import Any

from webnovel.modules.audit.contract import AuditEntry, AuditService
from webnovel.modules.audit.repository import AuditRepository


class AuditServiceImpl(AuditService):
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def record(
        self,
        action: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return await self._repository.append(
            action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
        )

    async def list(self, limit: int = 100) -> list[AuditEntry]:
        return await self._repository.list(limit)
