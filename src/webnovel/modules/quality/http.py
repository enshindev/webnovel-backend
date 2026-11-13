from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

from webnovel.entrypoints.api.deps import BudgetGuardDep, QualityServiceDep

router = APIRouter(tags=["quality"])


class QualityCheckBody(BaseModel):
    chapter_id: UUID


class QualityIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    severity: str
    message: str
    location: dict[str, Any] | None
    suggestion: str | None


class QualityReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    chapter_id: UUID
    version_id: UUID
    status: str
    score: int
    issues: list[QualityIssueOut]
    metrics: dict[str, Any]
    created_at: datetime
    stage: str


class QualityReportList(BaseModel):
    items: list[QualityReportOut]


@router.post(
    "/works/{work_id}/quality-checks",
    response_model=QualityReportOut,
    status_code=status.HTTP_201_CREATED,
)
async def run_quality_check(
    work_id: UUID, body: QualityCheckBody, service: QualityServiceDep
) -> QualityReportOut:
    report = await service.check_chapter(work_id, body.chapter_id)
    return QualityReportOut.model_validate(report)


@router.post(
    "/works/{work_id}/quality-reviews",
    response_model=QualityReportOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_quality_review(
    work_id: UUID,
    body: QualityCheckBody,
    service: QualityServiceDep,
    guard: BudgetGuardDep,
) -> QualityReportOut:
    await guard.check()
    report = await service.start_review(work_id, body.chapter_id)
    return QualityReportOut.model_validate(report)


@router.get("/quality-reports/{report_id}", response_model=QualityReportOut)
async def get_quality_report(report_id: UUID, service: QualityServiceDep) -> QualityReportOut:
    return QualityReportOut.model_validate(await service.get_report(report_id))


@router.get("/works/{work_id}/quality-reports", response_model=QualityReportList)
async def list_quality_reports(work_id: UUID, service: QualityServiceDep) -> QualityReportList:
    reports = await service.list_reports(work_id)
    return QualityReportList(items=[QualityReportOut.model_validate(report) for report in reports])
