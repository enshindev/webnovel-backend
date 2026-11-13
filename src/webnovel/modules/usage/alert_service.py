from __future__ import annotations

from webnovel.modules.usage.alert_repository import BudgetAlertRecord, BudgetAlertRepository
from webnovel.modules.usage.budget import BudgetStatus


class BudgetAlertService:
    def __init__(self, repository: BudgetAlertRepository) -> None:
        self._repository = repository

    async def record(self, status: BudgetStatus) -> None:
        await self._repository.record(status)

    async def list(self, limit: int = 100) -> list[BudgetAlertRecord]:
        return await self._repository.list(limit)
