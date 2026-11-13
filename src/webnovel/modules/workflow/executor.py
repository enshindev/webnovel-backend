from __future__ import annotations

import json
from uuid import UUID

import structlog

from webnovel.infra.config import Settings
from webnovel.kernel.errors import ConflictError
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest
from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.usage.contract import UsageService
from webnovel.modules.workflow.contract import WorkflowRun
from webnovel.modules.workflow.repository import WorkflowRepository
from webnovel.modules.works.contract import WorkService

logger = structlog.get_logger(__name__)


class WorkflowExecutor:
    """执行当前 workflow 阶段，产出草稿工件；不自动推进、不写正文。"""

    def __init__(
        self,
        *,
        repository: WorkflowRepository,
        work_service: WorkService,
        model_client: ModelClient,
        settings: Settings,
        usage: UsageService | None = None,
    ) -> None:
        self._repository = repository
        self._work_service = work_service
        self._model_client = model_client
        self._settings = settings
        self._usage = usage

    async def execute(self, run_id: UUID) -> WorkflowRun:
        run = await self._repository.get(run_id)
        if run is None:
            raise ConflictError("workflow run not found", code="workflow.not_found")
        if run.status == "waiting_confirmation":
            run = await self._repository.claim(run_id)
            if run is None:
                raise ConflictError("workflow is not claimable", code="workflow.not_claimable")
        elif run.status != "executing":
            raise ConflictError(
                f"workflow is not executable: {run.status}", code="workflow.not_executable"
            )
        try:
            return await self._run_stage(run)
        except Exception as exc:
            await self._repository.save(run.id, status="failed", error=str(exc))
            raise

    async def _run_stage(self, run: WorkflowRun) -> WorkflowRun:
        work = await self._work_service.get(run.work_id)
        registry = PromptRegistry(self._settings.prompts_dir)
        prompt = registry.resolve("workflow/stage")
        rendered = render_prompt(
            prompt,
            {
                "stage": run.current_stage,
                "work": f"{work.title} / {work.genre or '未设题材'}",
                "artifacts": json.dumps(run.artifacts, ensure_ascii=False),
            },
            registry.load_includes(prompt),
        )
        result = await self._model_client.complete(
            ModelRequest(
                model=self._settings.llm_model,
                messages=[ChatMessage(role="user", content=rendered)],
                max_tokens=2_000,
            )
        )
        if self._usage is not None:
            await self._usage.record_llm(
                work_id=run.work_id,
                generation_id=None,
                provider=self._settings.llm_provider,
                model=self._settings.llm_model,
                task_type="workflow",
                prompt_tokens=estimate_tokens(rendered),
                completion_tokens=estimate_tokens(result),
                estimated=True,
            )
        artifacts = dict(run.artifacts)
        artifacts[run.current_stage] = {
            "text": result,
            "model": self._settings.llm_model,
            "prompt_version": prompt.version,
        }
        updated = await self._repository.save(
            run.id, artifacts=artifacts, status="waiting_confirmation"
        )
        if updated is None:
            raise ConflictError("workflow run disappeared", code="workflow.not_found")
        logger.info("workflow.stage_executed", run_id=str(run.id), stage=run.current_stage)
        return updated
