from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app
from webnovel.entrypoints.api.deps import get_audit_service
from webnovel.modules.audit.contract import AuditEntry


class FakeAuditService:
    async def list(self, limit: int = 100) -> list[AuditEntry]:
        return [
            AuditEntry(
                id=1,
                ts=datetime.now(UTC),
                actor="local",
                action="work.create",
                target_type="work",
                target_id="1",
                metadata={},
                prev_hash=None,
                hash="hash",
            )
        ]


def test_list_audit_logs() -> None:
    app = create_app()
    app.dependency_overrides[get_audit_service] = lambda: FakeAuditService()
    client = TestClient(app)
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 200
    assert response.json()[0]["action"] == "work.create"
