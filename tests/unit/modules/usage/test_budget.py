from __future__ import annotations

from uuid import UUID

import pytest

from webnovel.kernel.errors import ConflictError
from webnovel.modules.usage.budget import BudgetGuard
from webnovel.modules.usage.contract import UsageEntry, UsageSummary


class FakeUsageService:
    def __init__(self, daily: float) -> None:
        self.daily = daily

    async def record_llm(self, **kwargs: object) -> None:
        return None

    async def list(self, work_id: UUID, limit: int = 100) -> list[UsageEntry]:
        return []

    async def summary(self, work_id: UUID) -> UsageSummary:
        return UsageSummary(0, 0, 0, 0, 0.0, "CNY")

    async def daily_cost(self) -> float:
        return self.daily


async def test_budget_warning_state() -> None:
    status = await BudgetGuard(FakeUsageService(8.0), 10.0).status()
    assert status.state == "warning"
    assert status.ratio == 0.8


async def test_budget_warning_records_alert() -> None:
    recorded = []

    async def record(status: object) -> None:
        recorded.append(status)

    guard = BudgetGuard(FakeUsageService(8.0), 10.0, record)
    await guard.check()
    assert len(recorded) == 1


async def test_budget_exceeded_blocks() -> None:
    guard = BudgetGuard(FakeUsageService(10.1), 10.0)
    with pytest.raises(ConflictError, match="daily budget exceeded"):
        await guard.check()


async def test_budget_disabled_without_limit() -> None:
    status = await BudgetGuard(FakeUsageService(100.0), None).status()
    assert status.state == "disabled"
