from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import (
    WorkflowExecutorDep,
    WorkflowQueueDep,
    WorkflowServiceDep,
)

router = APIRouter(tags=["workflow"])


class WorkflowCreate(BaseModel):
    template: str = "outline_to_draft"


class WorkflowAdvance(BaseModel):
    artifact: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    template: str
    status: str
    current_stage: str
    stages: list[str]
    artifacts: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime


@router.post("/works/{work_id}/workflow-runs", response_model=WorkflowOut, status_code=201)
async def create_workflow(
    work_id: UUID, body: WorkflowCreate, service: WorkflowServiceDep
) -> WorkflowOut:
    return WorkflowOut.model_validate(await service.create(work_id, body.template))


@router.get("/works/{work_id}/workflow-runs", response_model=list[WorkflowOut])
async def list_workflows(work_id: UUID, service: WorkflowServiceDep) -> list[WorkflowOut]:
    return [WorkflowOut.model_validate(item) for item in await service.list(work_id)]


@router.get("/workflow-runs/{run_id}", response_model=WorkflowOut)
async def get_workflow(run_id: UUID, service: WorkflowServiceDep) -> WorkflowOut:
    return WorkflowOut.model_validate(await service.get(run_id))


@router.post("/workflow-runs/{run_id}/advance", response_model=WorkflowOut)
async def advance_workflow(
    run_id: UUID, body: WorkflowAdvance, service: WorkflowServiceDep
) -> WorkflowOut:
    return WorkflowOut.model_validate(await service.advance(run_id, body.artifact, body.note))


@router.post("/workflow-runs/{run_id}/execute", response_model=WorkflowOut)
async def execute_workflow_stage(run_id: UUID, executor: WorkflowExecutorDep) -> WorkflowOut:
    return WorkflowOut.model_validate(await executor.execute(run_id))


@router.post(
    "/workflow-runs/{run_id}/execute-async",
    response_model=WorkflowOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_workflow_stage_async(
    run_id: UUID, service: WorkflowServiceDep, queue: WorkflowQueueDep
) -> WorkflowOut:
    run = await service.claim_execution(run_id)
    await queue.enqueue_workflow(run.id)
    return WorkflowOut.model_validate(run)


@router.post(
    "/workflow-runs/{run_id}/run-all",
    response_model=WorkflowOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_workflow_all(
    run_id: UUID, service: WorkflowServiceDep, queue: WorkflowQueueDep
) -> WorkflowOut:
    run = await service.get(run_id)
    await queue.enqueue_workflow_all(run.id)
    return WorkflowOut.model_validate(run)


@router.post("/workflow-runs/{run_id}/cancel", response_model=WorkflowOut)
async def cancel_workflow(run_id: UUID, service: WorkflowServiceDep) -> WorkflowOut:
    return WorkflowOut.model_validate(await service.cancel(run_id))
