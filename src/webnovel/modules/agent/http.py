from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from webnovel.entrypoints.api.deps import AgentServiceDep

router = APIRouter(prefix="/agent/runs", tags=["agent"])


class AgentRunCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=4_000)
    work_id: UUID | None = None
    experiment: str = Field(default="assistant", max_length=64)


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    payload: dict[str, Any]
    status: str


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: str
    work_id: UUID | None
    experiment: str
    goal: str
    status: str
    state: dict[str, Any]
    steps: int
    tokens: int
    cost: float
    error: str | None
    created_at: datetime
    updated_at: datetime
    pending_approvals: list[ApprovalOut]


class ApprovalCreate(BaseModel):
    action: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = None


@router.post("", response_model=AgentRunOut, status_code=status.HTTP_202_ACCEPTED)
async def create_agent_run(body: AgentRunCreate, service: AgentServiceDep) -> AgentRunOut:
    run = await service.create(body.goal, body.work_id, body.experiment)
    return AgentRunOut.model_validate(run)


@router.get("/{run_id}", response_model=AgentRunOut)
async def get_agent_run(run_id: UUID, service: AgentServiceDep) -> AgentRunOut:
    return AgentRunOut.model_validate(await service.get(run_id))


@router.post("/{run_id}/cancel", response_model=AgentRunOut)
async def cancel_agent_run(run_id: UUID, service: AgentServiceDep) -> AgentRunOut:
    return AgentRunOut.model_validate(await service.cancel(run_id))


@router.post("/{run_id}/approvals", response_model=AgentRunOut)
async def request_approval(
    run_id: UUID, body: ApprovalCreate, service: AgentServiceDep
) -> AgentRunOut:
    return AgentRunOut.model_validate(
        await service.request_approval(run_id, body.action, body.payload)
    )


@router.post("/{run_id}/approvals/{approval_id}", response_model=AgentRunOut)
async def decide_approval(
    run_id: UUID,
    approval_id: UUID,
    body: ApprovalDecision,
    service: AgentServiceDep,
) -> AgentRunOut:
    return AgentRunOut.model_validate(
        await service.decide(run_id, approval_id, body.decision, body.note)
    )
