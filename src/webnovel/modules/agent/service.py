from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from webnovel.kernel.errors import ConflictError, NotFoundError, ValidationError
from webnovel.modules.agent.contract import AgentRun, AgentService
from webnovel.modules.agent.repository import AgentRepository


class AgentServiceImpl(AgentService):
    def __init__(
        self,
        repository: AgentRepository,
        enqueue: Callable[[UUID], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self._enqueue = enqueue

    async def create(self, goal: str, work_id: UUID | None, experiment: str) -> AgentRun:
        goal = goal.strip()
        if not goal:
            raise ValidationError("goal required", code="agent.goal_required")
        run = await self._repository.create(goal, work_id, experiment)
        if self._enqueue is not None:
            await self._enqueue(run.id)
        return run

    async def get(self, run_id: UUID) -> AgentRun:
        run = await self._repository.get(run_id)
        if run is None:
            raise NotFoundError(f"agent run not found: {run_id}", code="agent.not_found")
        return run

    async def cancel(self, run_id: UUID) -> AgentRun:
        run = await self.get(run_id)
        if run.status in {"succeeded", "failed", "cancelled"}:
            return run
        updated = await self._repository.save(run_id, status="cancelled")
        if updated is None:
            raise NotFoundError(f"agent run not found: {run_id}", code="agent.not_found")
        return updated

    async def request_approval(
        self, run_id: UUID, action: str, payload: dict[str, Any]
    ) -> AgentRun:
        await self.get(run_id)
        if not action.strip():
            raise ValidationError("action required", code="agent.action_required")
        run = await self._repository.add_approval(run_id, action, payload)
        if run is None:
            raise NotFoundError(f"agent run not found: {run_id}", code="agent.not_found")
        return run

    async def decide(
        self, run_id: UUID, approval_id: UUID, decision: str, note: str | None
    ) -> AgentRun:
        if decision not in {"approve", "reject"}:
            raise ValidationError("invalid decision", code="agent.invalid_decision")
        run = await self._repository.decide(run_id, approval_id, decision)
        if run is None:
            raise ConflictError(
                "approval not found or already decided", code="agent.approval_conflict"
            )
        if note:
            state = dict(run.state)
            state.setdefault("approval_notes", []).append(
                {"approval_id": str(approval_id), "note": note}
            )
            run = await self._repository.save(run.id, state=state) or run
        if run.status == "running" and self._enqueue is not None:
            await self._enqueue(run.id)
        return run
