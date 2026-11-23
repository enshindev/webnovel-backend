from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


async def record_media_usage(
    usage: UsageService | None,
    *,
    work_id: UUID | None,
    task: str,
    model: str,
    prompt_units: int,
    output_units: int,
) -> None:
    if usage is None:
        return
    await usage.record_llm(
        work_id=work_id,
        generation_id=None,
        provider="multimodal",
        model=model or "multimodal",
        task_type=task,
        prompt_tokens=max(1, prompt_units // 4),
        completion_tokens=max(1, output_units // 4),
        estimated=True,
    )


@dataclass(frozen=True, slots=True)
class UsageEntry:
    id: int
    ts: datetime
    work_id: UUID | None
    generation_id: UUID | None
    provider: str
    model: str
    task_type: str | None
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    cost: float
    currency: str
    estimated: bool


@dataclass(frozen=True, slots=True)
class UsageBucket:
    key: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost: float
    currency: str


@dataclass(frozen=True, slots=True)
class UsageSummary:
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    cost: float
    currency: str


@dataclass(frozen=True, slots=True)
class UsageOverview:
    summary: UsageSummary
    by_model: list[UsageBucket]
    by_task: list[UsageBucket]
    by_day: list[UsageBucket]


class UsageService(Protocol):
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
    ) -> None: ...

    async def list(self, work_id: UUID, limit: int = 100) -> Sequence[UsageEntry]: ...

    async def summary(self, work_id: UUID) -> UsageSummary: ...

    async def daily_cost(self) -> float: ...

    async def breakdown(
        self, work_id: UUID, group_by: str, days: int = 30
    ) -> Sequence[UsageBucket]: ...

    async def overview(self, days: int = 30) -> UsageOverview: ...
