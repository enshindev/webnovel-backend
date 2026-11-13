from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from webnovel.modules.audit.contract import AuditEntry
from webnovel.modules.audit.service import AuditServiceImpl


class FakeAuditRepository:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def append(
        self,
        action: str,
        *,
        target_type: str | None,
        target_id: str | None,
        metadata: dict[str, Any],
    ) -> AuditEntry:
        entry = AuditEntry(
            id=len(self.entries) + 1,
            ts=datetime.now(UTC),
            actor="local",
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
            prev_hash=self.entries[-1].hash if self.entries else None,
            hash=f"hash-{len(self.entries) + 1}",
        )
        self.entries.append(entry)
        return entry

    async def list(self, limit: int) -> list[AuditEntry]:
        return list(reversed(self.entries))[:limit]


async def test_audit_chain_and_list() -> None:
    repo = FakeAuditRepository()
    service = AuditServiceImpl(repo)
    first = await service.record("work.create", target_type="work", target_id="1")
    second = await service.record("work.update", target_type="work", target_id="1")
    assert first.prev_hash is None
    assert second.prev_hash == first.hash
    assert (await service.list())[0].action == "work.update"
