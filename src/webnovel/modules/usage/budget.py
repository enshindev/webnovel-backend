from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

from webnovel.kernel.errors import ConflictError
from webnovel.modules.usage.contract import UsageService

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    limit: float | None
    spent: float
    ratio: float
    state: str


class BudgetGuard:
    def __init__(
        self,
        usage: UsageService,
        limit: float | None,
        recorder: Callable[[BudgetStatus], Awaitable[None]] | None = None,
    ) -> None:
        self._usage = usage
        self._limit = limit
        self._recorder = recorder

    async def status(self) -> BudgetStatus:
        spent = await self._usage.daily_cost()
        if self._limit is None or self._limit <= 0:
            return BudgetStatus(limit=self._limit, spent=spent, ratio=0.0, state="disabled")
        ratio = spent / self._limit
        state = "exceeded" if ratio >= 1 else "warning" if ratio >= 0.8 else "ok"
        return BudgetStatus(limit=self._limit, spent=spent, ratio=round(ratio, 4), state=state)

    async def check(self) -> None:
        status = await self.status()
        if status.state in {"warning", "exceeded"} and self._recorder is not None:
            try:
                await self._recorder(status)
            except Exception:
                logger.exception("usage.budget_alert_failed")
        if status.state == "warning":
            logger.warning("usage.budget_warning", spent=status.spent, limit=status.limit)
        if status.state == "exceeded":
            raise ConflictError(
                f"daily budget exceeded: {status.spent:.2f}/{status.limit:.2f}",
                code="budget.exceeded",
            )
