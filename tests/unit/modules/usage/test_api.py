from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from webnovel.entrypoints.api.app import create_app
from webnovel.entrypoints.api.deps import get_usage_service
from webnovel.modules.usage.contract import UsageBucket, UsageEntry, UsageSummary


class FakeUsageService:
    async def list(self, work_id: object, limit: int = 100) -> list[UsageEntry]:
        return [
            UsageEntry(
                id=1,
                ts=datetime.now(UTC),
                work_id=uuid4(),
                generation_id=None,
                provider="fake",
                model="m",
                task_type="summary",
                prompt_tokens=10,
                completion_tokens=5,
                cached_tokens=0,
                cost=0.01,
                currency="CNY",
                estimated=True,
            )
        ]

    async def summary(self, work_id: object) -> UsageSummary:
        return UsageSummary(1, 10, 5, 0, 0.01, "CNY")

    async def breakdown(self, work_id: object, group_by: str, days: int = 30) -> list[UsageBucket]:
        return [
            UsageBucket("m", 1, 10, 5, 0.01, "CNY"),
        ]


def test_usage_endpoints() -> None:
    app = create_app()
    app.dependency_overrides[get_usage_service] = lambda: FakeUsageService()
    client = TestClient(app)
    work_id = uuid4()
    entries = client.get(f"/api/v1/works/{work_id}/usage")
    assert entries.status_code == 200
    assert entries.json()["items"][0]["model"] == "m"
    summary = client.get(f"/api/v1/works/{work_id}/usage/summary")
    assert summary.status_code == 200
    assert summary.json()["calls"] == 1
    breakdown = client.get(f"/api/v1/works/{work_id}/usage/breakdown?group_by=model")
    assert breakdown.status_code == 200
    assert breakdown.json()["items"][0]["key"] == "m"
