from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.modules.workflow.contract import WorkflowRun
from webnovel.modules.workflow.service import WorkflowServiceImpl
from webnovel.modules.works.contract import Work


class FakeWorkService:
    async def get(self, work_id: UUID) -> Work:
        now = datetime.now(UTC)
        return Work(work_id, "t", None, "draft", now, now)


class FakeWorkflowRepository:
    def __init__(self) -> None:
        self.run: WorkflowRun | None = None

    async def create(self, work_id: UUID, template: str, stages: list[str]) -> WorkflowRun:
        now = datetime.now(UTC)
        self.run = WorkflowRun(
            uuid4(),
            work_id,
            template,
            "waiting_confirmation",
            stages[0],
            stages,
            {},
            None,
            now,
            now,
        )
        return self.run

    async def get(self, run_id: UUID) -> WorkflowRun | None:
        return self.run

    async def claim(self, run_id: UUID) -> WorkflowRun | None:
        if self.run is None or self.run.status != "waiting_confirmation":
            return None
        self.run = replace(self.run, status="executing")
        return self.run

    async def list(self, work_id: UUID) -> list[WorkflowRun]:
        return [self.run] if self.run else []

    async def save(self, run_id: UUID, **values: Any) -> WorkflowRun | None:
        if self.run is None:
            return None
        self.run = replace(self.run, **values)
        return self.run


async def test_workflow_advances_to_completion() -> None:
    repo = FakeWorkflowRepository()
    service = WorkflowServiceImpl(repo, FakeWorkService())  # type: ignore[arg-type]
    run = await service.create(uuid4())
    assert run.current_stage == "outline"
    assert run.status == "waiting_confirmation"
    for stage in ("outline", "chapters", "writing"):
        run = await service.advance(run.id, {"stage": stage}, None)
        assert stage in run.artifacts
    run = await service.advance(run.id, {"stage": "review"}, "ok")
    assert run.status == "completed"
    assert run.current_stage == "done"


class FakeModel:
    async def complete(self, request: object) -> str:
        return "阶段草稿"


async def test_workflow_executor_produces_artifact() -> None:
    from webnovel.infra.config import Settings
    from webnovel.modules.workflow.executor import WorkflowExecutor

    repo = FakeWorkflowRepository()
    service = WorkflowServiceImpl(repo, FakeWorkService())  # type: ignore[arg-type]
    run = await service.create(uuid4())
    executor = WorkflowExecutor(
        repository=repo,
        work_service=FakeWorkService(),  # type: ignore[arg-type]
        model_client=FakeModel(),  # type: ignore[arg-type]
        settings=Settings(),
    )
    updated = await executor.execute(run.id)
    assert updated.artifacts["outline"]["text"] == "阶段草稿"
    assert updated.status == "waiting_confirmation"


async def test_workflow_claim_is_exclusive() -> None:
    from webnovel.kernel.errors import ConflictError

    repo = FakeWorkflowRepository()
    service = WorkflowServiceImpl(repo, FakeWorkService())  # type: ignore[arg-type]
    run = await service.create(uuid4())
    claimed = await service.claim_execution(run.id)
    assert claimed.status == "executing"
    try:
        await service.claim_execution(run.id)
    except ConflictError as exc:
        assert exc.code == "workflow.not_claimable"
    else:
        raise AssertionError("expected conflict")


async def test_workflow_auto_runner_completes_all_stages() -> None:
    from webnovel.infra.config import Settings
    from webnovel.modules.workflow.auto import WorkflowAutoRunner
    from webnovel.modules.workflow.executor import WorkflowExecutor

    repo = FakeWorkflowRepository()
    service = WorkflowServiceImpl(repo, FakeWorkService())  # type: ignore[arg-type]
    run = await service.create(uuid4())
    executor = WorkflowExecutor(
        repository=repo,
        work_service=FakeWorkService(),  # type: ignore[arg-type]
        model_client=FakeModel(),  # type: ignore[arg-type]
        settings=Settings(),
    )
    completed = await WorkflowAutoRunner(executor, service).run_all(str(run.id))
    assert completed.status == "completed"
    assert completed.current_stage == "done"
    assert set(completed.artifacts) == {"outline", "chapters", "writing", "review"}
