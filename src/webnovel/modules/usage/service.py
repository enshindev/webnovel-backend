from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from webnovel.modules.usage.contract import (
    UsageBucket,
    UsageEntry,
    UsageOverview,
    UsageService,
    UsageSummary,
)
from webnovel.modules.usage.pricing import Pricing
from webnovel.modules.usage.repository import UsageRepository


class UsageServiceImpl(UsageService):
    def __init__(self, repository: UsageRepository, pricing: Pricing) -> None:
        self._repository = repository
        self._pricing = pricing

    async def record_llm(
        self,
        *,
        work_id: UUID | None,
        generation_id: UUID | None,
        provider: str,
        model: str,
        task_type: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        estimated: bool = False,
    ) -> None:
        price = self._pricing.price_for(model)
        billable_prompt = max(0, prompt_tokens - cached_tokens)
        cost = (
            billable_prompt * price.input_per_million
            + cached_tokens * price.cached_input_per_million
            + completion_tokens * price.output_per_million
        ) / 1_000_000
        await self._repository.add(
            work_id=work_id,
            generation_id=generation_id,
            provider=provider,
            model=model,
            task_type=task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            price_snapshot={
                "input_per_million": price.input_per_million,
                "output_per_million": price.output_per_million,
                "cached_input_per_million": price.cached_input_per_million,
            },
            cost=cost,
            currency=self._pricing.currency,
            estimated=estimated,
        )

    async def list(self, work_id: UUID, limit: int = 100) -> Sequence[UsageEntry]:
        return await self._repository.list(work_id, limit)

    async def summary(self, work_id: UUID) -> UsageSummary:
        return await self._repository.summary(work_id)

    async def daily_cost(self) -> float:
        return await self._repository.daily_cost()

    async def overview(self, days: int = 30) -> UsageOverview:
        return await self._repository.overview(max(1, min(days, 365)))

    async def breakdown(
        self, work_id: UUID, group_by: str, days: int = 30
    ) -> Sequence[UsageBucket]:
        if group_by not in {"model", "task", "day"}:
            raise ValueError(f"unsupported group_by: {group_by}")
        return await self._repository.breakdown(work_id, group_by, days)
