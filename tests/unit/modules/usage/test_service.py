from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from webnovel.modules.usage.contract import UsageEntry, UsageSummary
from webnovel.modules.usage.pricing import Price, Pricing
from webnovel.modules.usage.service import UsageServiceImpl


class FakeUsageRepository:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    async def add(self, **kwargs: Any) -> None:
        self.entries.append(kwargs)

    async def list(self, work_id: UUID, limit: int) -> list[UsageEntry]:
        return []

    async def summary(self, work_id: UUID) -> UsageSummary:
        return UsageSummary(1, 100, 50, 0, 0.1, "CNY")


async def test_record_computes_cost_and_price_snapshot() -> None:
    repo = FakeUsageRepository()
    service = UsageServiceImpl(
        repo, Pricing(models={"m": Price(input_per_million=2.0, output_per_million=8.0)})
    )
    await service.record_llm(
        work_id=uuid4(),
        generation_id=uuid4(),
        provider="openai-compatible",
        model="m",
        task_type="continue",
        prompt_tokens=1_000,
        completion_tokens=500,
    )
    entry = repo.entries[0]
    assert entry["cost"] == (1_000 * 2.0 + 500 * 8.0) / 1_000_000
    assert entry["price_snapshot"]["output_per_million"] == 8.0
    assert isinstance(entry["work_id"], UUID)
