from __future__ import annotations

from typing import Any
from uuid import UUID

from webnovel.kernel.errors import ConflictError, NotFoundError, ValidationError
from webnovel.modules.workflow.contract import WorkflowRun, WorkflowService
from webnovel.modules.workflow.repository import WorkflowRepository
from webnovel.modules.works.contract import WorkService

_TEMPLATES = {
    "outline_to_draft": ["outline", "chapters", "writing", "review"],
}


class WorkflowServiceImpl(WorkflowService):
    def __init__(self, repository: WorkflowRepository, work_service: WorkService) -> None:
        self._repository = repository
        self._work_service = work_service

    async def create(self, work_id: UUID, template: str = "outline_to_draft") -> WorkflowRun:
        await self._work_service.get(work_id)
        stages = _TEMPLATES.get(template)
        if stages is None:
            raise ValidationError("unknown workflow template", code="workflow.template_invalid")
        return await self._repository.create(work_id, template, stages)

    async def get(self, run_id: UUID) -> WorkflowRun:
        run = await self._repository.get(run_id)
        if run is None:
            raise NotFoundError(f"workflow run not found: {run_id}", code="workflow.not_found")
        return run

    async def list(self, work_id: UUID) -> list[WorkflowRun]:
        await self._work_service.get(work_id)
        return await self._repository.list(work_id)

    async def claim_execution(self, run_id: UUID) -> WorkflowRun:
        run = await self._repository.claim(run_id)
        if run is None:
            raise ConflictError("workflow is not claimable", code="workflow.not_claimable")
        return run

    async def advance(
        self, run_id: UUID, artifact: dict[str, Any] | None, note: str | None
    ) -> WorkflowRun:
        run = await self.get(run_id)
        if run.status != "waiting_confirmation":
            raise ConflictError(
                f"workflow is not waiting: {run.status}", code="workflow.not_waiting"
            )
        artifacts = dict(run.artifacts)
        payload: dict[str, Any] = dict(artifact or {})
        if note:
            payload["note"] = note
        artifacts[run.current_stage] = payload
        index = run.stages.index(run.current_stage)
        if index + 1 >= len(run.stages):
            updated = await self._repository.save(
                run.id, status="completed", current_stage="done", artifacts=artifacts
            )
        else:
            updated = await self._repository.save(
                run.id,
                status="waiting_confirmation",
                current_stage=run.stages[index + 1],
                artifacts=artifacts,
            )
        if updated is None:
            raise NotFoundError(f"workflow run not found: {run_id}", code="workflow.not_found")
        return updated

    async def cancel(self, run_id: UUID) -> WorkflowRun:
        run = await self.get(run_id)
        if run.status in {"completed", "cancelled"}:
            return run
        updated = await self._repository.save(run.id, status="cancelled")
        if updated is None:
            raise NotFoundError(f"workflow run not found: {run_id}", code="workflow.not_found")
        return updated
