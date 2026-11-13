from __future__ import annotations

from collections.abc import Awaitable, Callable
from importlib.util import find_spec
from uuid import UUID

from webnovel.kernel.errors import ConflictError, NotFoundError, ValidationError
from webnovel.modules.audit.contract import AuditRecorder
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.export.contract import ExportJob, ExportService
from webnovel.modules.export.gate import evaluate_gate
from webnovel.modules.export.repository import ExportRepository
from webnovel.modules.outbox.contract import OutboxService
from webnovel.modules.quality.contract import QualityService
from webnovel.modules.works.contract import WorkService


class ExportServiceImpl(ExportService):
    def __init__(
        self,
        repository: ExportRepository,
        *,
        chapter_service: ChapterService,
        quality_service: QualityService,
        work_service: WorkService,
        enqueue: Callable[[UUID], Awaitable[None]] | None = None,
        audit: AuditRecorder | None = None,
        outbox: OutboxService | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._quality_service = quality_service
        self._work_service = work_service
        self._enqueue = enqueue
        self._audit = audit
        self._outbox = outbox

    async def create(self, work_id: UUID, fmt: str) -> ExportJob:
        if fmt not in {"txt", "docx"}:
            raise ValidationError("unsupported export format", code="export.unsupported_format")
        if fmt == "docx" and find_spec("docx") is None:
            raise ValidationError(
                "docx export requires the export extra", code="export.docx_unavailable"
            )
        await self._work_service.get(work_id)
        gate = await evaluate_gate(
            work_id,
            chapter_service=self._chapter_service,
            quality_service=self._quality_service,
        )
        if gate.blocking:
            detail = "; ".join(issue.message for issue in gate.blocking[:5])
            raise ConflictError(f"export blocked: {detail}", code="export.gate_blocked")
        job = await self._repository.create(work_id, fmt)
        if self._enqueue is not None:
            await self._enqueue(job.id)
        if self._audit is not None:
            await self._audit.record(
                "export.create",
                target_type="export_job",
                target_id=str(job.id),
                metadata={"format": fmt},
            )
        if self._outbox is not None:
            await self._outbox.emit("export_job", job.id, "export.created", {"format": fmt})
        return job

    async def get(self, job_id: UUID) -> ExportJob:
        job = await self._repository.get(job_id)
        if job is None:
            raise NotFoundError(f"export job not found: {job_id}", code="export.not_found")
        return job
