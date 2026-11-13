from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.quality.contract import QualityIssue, QualityReport
from webnovel.modules.quality.models import QualityCheckModel, QualityIssueModel

RULE_VERSION = "machine.v1"


class QualityRepository(Protocol):
    async def save(self, report: QualityReport) -> QualityReport: ...

    async def create_pending(
        self, *, work_id: UUID, chapter_id: UUID, version_id: UUID, stage: str
    ) -> QualityReport: ...

    async def save_review(
        self,
        report_id: UUID,
        *,
        status: str,
        score: int,
        metrics: dict[str, Any],
        issues: list[QualityIssue],
    ) -> QualityReport | None: ...

    async def get(self, report_id: UUID) -> QualityReport | None: ...

    async def list(self, work_id: UUID) -> list[QualityReport]: ...


def _issue_to_domain(model: QualityIssueModel) -> QualityIssue:
    location: dict[str, Any] | None = None
    if model.location:
        try:
            location = cast(dict[str, Any], json.loads(model.location))
        except json.JSONDecodeError:
            location = {"raw": model.location}
    return QualityIssue(
        code=model.type,
        severity=model.severity,
        message=model.detail,
        location=location,
        suggestion=model.suggestion,
    )


def _to_domain(model: QualityCheckModel, issues: list[QualityIssueModel]) -> QualityReport:
    summary = cast(dict[str, Any], model.summary)
    metrics = cast(dict[str, Any], summary.get("metrics", {}))
    return QualityReport(
        id=model.id,
        work_id=model.work_id,
        chapter_id=model.chapter_id or UUID(int=0),
        version_id=model.version_id or UUID(int=0),
        status=str(summary.get("result_status", model.status)),
        score=int(summary.get("score", 0)),
        issues=[_issue_to_domain(issue) for issue in issues],
        metrics=metrics,
        created_at=model.created_at,
        stage=model.stage,
    )


class SqlAlchemyQualityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, report: QualityReport) -> QualityReport:
        check = QualityCheckModel(
            work_id=report.work_id,
            chapter_id=report.chapter_id,
            version_id=report.version_id,
            status="succeeded",
            rule_version=RULE_VERSION,
            stage="chapter",
            channel="male",
            summary={
                "result_status": report.status,
                "score": report.score,
                "metrics": report.metrics,
            },
            finished_at=datetime.now(UTC),
        )
        self._session.add(check)
        await self._session.flush()

        issues = [
            QualityIssueModel(
                check_id=check.id,
                severity=issue.severity,
                type=issue.code,
                location=json.dumps(issue.location, ensure_ascii=False) if issue.location else None,
                detail=issue.message,
                suggestion=issue.suggestion,
            )
            for issue in report.issues
        ]
        self._session.add_all(issues)
        await self._session.flush()
        await self._session.refresh(check)
        return _to_domain(check, issues)

    async def create_pending(
        self, *, work_id: UUID, chapter_id: UUID, version_id: UUID, stage: str
    ) -> QualityReport:
        check = QualityCheckModel(
            work_id=work_id,
            chapter_id=chapter_id,
            version_id=version_id,
            status="queued",
            rule_version="llm.v1",
            stage=stage,
            channel="male",
            summary={"result_status": "queued", "score": 0, "metrics": {}},
        )
        self._session.add(check)
        await self._session.flush()
        await self._session.refresh(check)
        return _to_domain(check, [])

    async def save_review(
        self,
        report_id: UUID,
        *,
        status: str,
        score: int,
        metrics: dict[str, Any],
        issues: list[QualityIssue],
    ) -> QualityReport | None:
        check = await self._session.get(QualityCheckModel, report_id)
        if check is None:
            return None
        check.status = "succeeded" if status != "failed" else "failed"
        check.finished_at = datetime.now(UTC)
        check.summary = {
            "result_status": status,
            "score": score,
            "metrics": metrics,
        }
        await self._session.execute(
            delete(QualityIssueModel).where(QualityIssueModel.check_id == check.id)
        )
        models = [
            QualityIssueModel(
                check_id=check.id,
                severity=issue.severity,
                type=issue.code,
                location=json.dumps(issue.location, ensure_ascii=False) if issue.location else None,
                detail=issue.message,
                suggestion=issue.suggestion,
            )
            for issue in issues
        ]
        self._session.add_all(models)
        await self._session.flush()
        await self._session.refresh(check)
        return _to_domain(check, models)

    async def get(self, report_id: UUID) -> QualityReport | None:
        check = await self._session.get(QualityCheckModel, report_id)
        if check is None:
            return None
        stmt = select(QualityIssueModel).where(QualityIssueModel.check_id == check.id)
        issues = (await self._session.execute(stmt)).scalars().all()
        return _to_domain(check, list(issues))

    async def list(self, work_id: UUID) -> list[QualityReport]:
        stmt = (
            select(QualityCheckModel)
            .where(QualityCheckModel.work_id == work_id)
            .order_by(QualityCheckModel.created_at.desc())
        )
        checks = (await self._session.execute(stmt)).scalars().all()
        reports: list[QualityReport] = []
        for check in checks:
            issue_stmt = select(QualityIssueModel).where(QualityIssueModel.check_id == check.id)
            issues = (await self._session.execute(issue_stmt)).scalars().all()
            reports.append(_to_domain(check, list(issues)))
        return reports
