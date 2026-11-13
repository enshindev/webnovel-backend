from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WorkflowRun:
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


class WorkflowService(Protocol):
    async def create(self, work_id: UUID, template: str = "outline_to_draft") -> WorkflowRun: ...

    async def get(self, run_id: UUID) -> WorkflowRun: ...

    async def list(self, work_id: UUID) -> list[WorkflowRun]: ...

    async def claim_execution(self, run_id: UUID) -> WorkflowRun: ...

    async def advance(
        self, run_id: UUID, artifact: dict[str, Any] | None, note: str | None
    ) -> WorkflowRun: ...

    async def cancel(self, run_id: UUID) -> WorkflowRun: ...
