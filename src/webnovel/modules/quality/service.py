from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from webnovel.kernel.errors import NotFoundError, ValidationError
from webnovel.modules.audit.contract import AuditRecorder
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.memory.contract import Contradiction
from webnovel.modules.outbox.contract import OutboxService
from webnovel.modules.quality.checker import check_chapter as run_machine_check
from webnovel.modules.quality.contract import QualityIssue, QualityReport, QualityService
from webnovel.modules.quality.repository import QualityRepository
from webnovel.modules.quality.rules import PlatformRules

logger = structlog.get_logger(__name__)


class QualityServiceImpl(QualityService):
    def __init__(
        self,
        repository: QualityRepository,
        chapter_service: ChapterService,
        rules: PlatformRules,
        enqueue: Callable[[UUID], Awaitable[None]] | None = None,
        audit: AuditRecorder | None = None,
        outbox: OutboxService | None = None,
        contradictions: Callable[[UUID], Awaitable[list[Contradiction]]] | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._rules = rules
        self._enqueue = enqueue
        self._audit = audit
        self._outbox = outbox
        self._contradictions = contradictions

    async def check_chapter(self, work_id: UUID, chapter_id: UUID) -> QualityReport:
        chapter = await self._chapter_service.get(chapter_id)
        if chapter.work_id != work_id:
            raise ValidationError("chapter does not belong to work", code="quality.work_mismatch")
        if chapter.current_version_id is None:
            raise ValidationError("chapter has no content to check", code="quality.empty_chapter")
        version = await self._chapter_service.get_version(chapter.id, chapter.current_version_id)
        chapters = await self._chapter_service.list(work_id)
        result = run_machine_check(
            version.content,
            chapter_numbers=[item.number for item in chapters],
            rules=self._rules,
        )
        issues = list(result.issues)
        contradictions = 0
        if self._contradictions is not None:
            try:
                for item in await self._contradictions(work_id):
                    if item.chapter_number != chapter.number:
                        continue
                    contradictions += 1
                    issues.append(
                        QualityIssue(
                            code=item.kind,
                            severity=item.severity,
                            message=item.message,
                            location={"chapter": chapter.number},
                        )
                    )
            except Exception:
                logger.exception("quality.contradiction_check_failed", work_id=str(work_id))
        status = result.status
        if any(issue.severity == "P0" for issue in issues):
            status = "failed"
        elif any(issue.severity == "P1" for issue in issues) and status == "passed":
            status = "warning"
        score = max(0, result.score - contradictions * 8)
        return await self._repository.save(
            QualityReport(
                id=uuid4(),
                work_id=work_id,
                chapter_id=chapter.id,
                version_id=version.id,
                status=status,
                score=score,
                issues=issues,
                metrics={**result.metrics, "contradictions": contradictions},
                created_at=datetime.now(UTC),
            )
        )

    async def start_review(self, work_id: UUID, chapter_id: UUID) -> QualityReport:
        chapter = await self._chapter_service.get(chapter_id)
        if chapter.work_id != work_id:
            raise ValidationError("chapter does not belong to work", code="quality.work_mismatch")
        if chapter.current_version_id is None:
            raise ValidationError("chapter has no content to review", code="quality.empty_chapter")
        report = await self._repository.create_pending(
            work_id=work_id,
            chapter_id=chapter.id,
            version_id=chapter.current_version_id,
            stage="polish",
        )
        if self._enqueue is not None:
            await self._enqueue(report.id)
        if self._audit is not None:
            await self._audit.record(
                "quality.review_start",
                target_type="quality_check",
                target_id=str(report.id),
                metadata={"chapter_id": str(chapter.id)},
            )
        if self._outbox is not None:
            await self._outbox.emit(
                "quality_check",
                report.id,
                "quality.review_started",
                {"chapter_id": str(chapter.id)},
            )
        return report

    async def get_report(self, report_id: UUID) -> QualityReport:
        report = await self._repository.get(report_id)
        if report is None:
            raise NotFoundError(f"quality report not found: {report_id}", code="quality.not_found")
        return report

    async def list_reports(self, work_id: UUID) -> list[QualityReport]:
        return await self._repository.list(work_id)
