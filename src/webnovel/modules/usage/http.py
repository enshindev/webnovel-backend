from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from webnovel.entrypoints.api.deps import BudgetAlertServiceDep, BudgetGuardDep, UsageServiceDep

router = APIRouter(tags=["usage"])


class UsageEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class UsageList(BaseModel):
    items: list[UsageEntryOut]


class UsageBucketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost: float
    currency: str


class UsageBreakdownOut(BaseModel):
    items: list[UsageBucketOut]


class BudgetAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day: str
    limit: float
    spent: float
    ratio: float
    state: str


class BudgetStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    limit: float | None
    spent: float
    ratio: float
    state: str


class UsageOverviewOut(BaseModel):
    summary: UsageSummaryOut
    by_model: list[UsageBucketOut]
    by_task: list[UsageBucketOut]
    by_day: list[UsageBucketOut]


class UsageSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calls: int
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    cost: float
    currency: str


@router.get("/works/{work_id}/usage", response_model=UsageList)
async def list_usage(work_id: UUID, service: UsageServiceDep, limit: int = 100) -> UsageList:
    entries = await service.list(work_id, min(max(limit, 1), 500))
    return UsageList(items=[UsageEntryOut.model_validate(entry) for entry in entries])


@router.get("/usage/budget/history", response_model=list[BudgetAlertOut])
async def budget_history(service: BudgetAlertServiceDep, limit: int = 100) -> list[BudgetAlertOut]:
    alerts = await service.list(min(max(limit, 1), 365))
    return [BudgetAlertOut.model_validate(alert) for alert in alerts]


@router.get("/usage/budget", response_model=BudgetStatusOut)
async def budget_status(guard: BudgetGuardDep) -> BudgetStatusOut:
    return BudgetStatusOut.model_validate(await guard.status())


@router.get("/works/{work_id}/usage/breakdown", response_model=UsageBreakdownOut)
async def usage_breakdown(
    work_id: UUID,
    service: UsageServiceDep,
    group_by: Literal["model", "task", "day"] = "model",
    days: int = 30,
) -> UsageBreakdownOut:
    buckets = await service.breakdown(work_id, group_by, min(max(days, 1), 365))
    return UsageBreakdownOut(items=[UsageBucketOut.model_validate(bucket) for bucket in buckets])


@router.get("/usage/overview", response_model=UsageOverviewOut)
async def usage_overview(service: UsageServiceDep, days: int = 30) -> UsageOverviewOut:
    overview = await service.overview(days)
    return UsageOverviewOut(
        summary=UsageSummaryOut.model_validate(overview.summary),
        by_model=[UsageBucketOut.model_validate(item) for item in overview.by_model],
        by_task=[UsageBucketOut.model_validate(item) for item in overview.by_task],
        by_day=[UsageBucketOut.model_validate(item) for item in overview.by_day],
    )


@router.get("/works/{work_id}/usage/summary", response_model=UsageSummaryOut)
async def usage_summary(work_id: UUID, service: UsageServiceDep) -> UsageSummaryOut:
    return UsageSummaryOut.model_validate(await service.summary(work_id))
