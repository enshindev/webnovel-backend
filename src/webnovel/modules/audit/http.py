from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from webnovel.entrypoints.api.deps import AuditServiceDep

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    actor: str
    action: str
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any]
    prev_hash: str | None
    hash: str


@router.get("", response_model=list[AuditEntryOut])
async def list_audit_logs(service: AuditServiceDep, limit: int = 100) -> list[AuditEntryOut]:
    entries = await service.list(min(max(limit, 1), 500))
    return [AuditEntryOut.model_validate(entry) for entry in entries]
