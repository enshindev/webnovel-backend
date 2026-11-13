from __future__ import annotations

from uuid import UUID

from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.export.contract import GateIssue, GateResult
from webnovel.modules.quality.contract import QualityReport, QualityService


async def evaluate_gate(
    work_id: UUID,
    *,
    chapter_service: ChapterService,
    quality_service: QualityService,
) -> GateResult:
    chapters = await chapter_service.list(work_id)
    if not chapters:
        return GateResult(
            blocking=[GateIssue(code="export.no_chapters", severity="P0", message="作品没有章节")]
        )

    reports = await quality_service.list_reports(work_id)
    blocking: list[GateIssue] = []
    warnings: list[GateIssue] = []

    for chapter in chapters:
        if chapter.current_version_id is None:
            blocking.append(
                GateIssue(
                    code="export.chapter_empty",
                    severity="P0",
                    message=f"第{chapter.number}章没有正文",
                    chapter_id=chapter.id,
                )
            )
            continue

        machine = _latest(reports, chapter.id, "chapter")
        review = _latest(reports, chapter.id, "polish")
        if machine is None:
            blocking.append(
                GateIssue(
                    code="quality.machine_missing",
                    severity="P0",
                    message=f"第{chapter.number}章缺少机检",
                    chapter_id=chapter.id,
                )
            )
        else:
            _append_quality_issues(machine, chapter.id, blocking, warnings)

        if review is None:
            warnings.append(
                GateIssue(
                    code="quality.review_missing",
                    severity="P1",
                    message=f"第{chapter.number}章还没有 LLM 审稿",
                    chapter_id=chapter.id,
                )
            )
        else:
            _append_quality_issues(review, chapter.id, blocking, warnings)

    return GateResult(blocking=blocking, warnings=warnings)


def _latest(reports: list[QualityReport], chapter_id: UUID, stage: str) -> QualityReport | None:
    for report in reports:
        if report.chapter_id == chapter_id and report.stage == stage:
            return report
    return None


def _append_quality_issues(
    report: QualityReport,
    chapter_id: UUID,
    blocking: list[GateIssue],
    warnings: list[GateIssue],
) -> None:
    if report.status == "failed":
        blocking.append(
            GateIssue(
                code="quality.failed",
                severity="P0",
                message=f"质检未通过（score={report.score}）",
                chapter_id=chapter_id,
            )
        )
    for issue in report.issues:
        target = blocking if issue.severity == "P0" else warnings if issue.severity == "P1" else []
        if target is not None:
            target.append(
                GateIssue(
                    code=issue.code,
                    severity=issue.severity,
                    message=issue.message,
                    chapter_id=chapter_id,
                )
            )
