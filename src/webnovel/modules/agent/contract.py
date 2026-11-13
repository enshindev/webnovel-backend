from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AgentApproval:
    id: UUID
    run_id: UUID
    action: str
    payload: dict[str, Any]
    status: str
    decided_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AgentRun:
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
    pending_approvals: list[AgentApproval] = field(default_factory=list)


class AgentService(Protocol):
    async def create(self, goal: str, work_id: UUID | None, experiment: str) -> AgentRun: ...

    async def get(self, run_id: UUID) -> AgentRun: ...

    async def cancel(self, run_id: UUID) -> AgentRun: ...

    async def request_approval(
        self, run_id: UUID, action: str, payload: dict[str, Any]
    ) -> AgentRun: ...

    async def decide(
        self, run_id: UUID, approval_id: UUID, decision: str, note: str | None
    ) -> AgentRun: ...
