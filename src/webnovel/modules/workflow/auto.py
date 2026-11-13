from __future__ import annotations

import structlog

from webnovel.kernel.errors import ConflictError
from webnovel.modules.workflow.contract import WorkflowRun
from webnovel.modules.workflow.executor import WorkflowExecutor
from webnovel.modules.workflow.service import WorkflowServiceImpl

logger = structlog.get_logger(__name__)


class WorkflowAutoRunner:
    """从当前阶段开始，逐阶段执行并自动推进到 completed。"""

    def __init__(self, executor: WorkflowExecutor, service: WorkflowServiceImpl) -> None:
        self._executor = executor
        self._service = service

    async def run_all(self, run_id: str) -> WorkflowRun:
        from uuid import UUID

        run = await self._service.claim_execution(UUID(run_id))
        for _ in range(16):
            if run.status == "completed":
                return run
            if run.status in {"waiting_confirmation", "executing"} and run.current_stage != "done":
                run = await self._executor.execute(run.id)
                if run.status != "waiting_confirmation":
                    raise ConflictError(
                        f"workflow stage did not complete: {run.status}",
                        code="workflow.stage_failed",
                    )
                run = await self._service.advance(run.id, {"auto": True}, "auto")
            else:
                raise ConflictError(
                    f"workflow cannot continue from {run.status}", code="workflow.not_executable"
                )
        raise ConflictError("workflow exceeded stage limit", code="workflow.stage_limit")
