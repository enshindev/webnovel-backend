from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.modules.agent.contract import AgentRun
from webnovel.modules.agent.service import AgentServiceImpl


class FakeAgentRepository:
    def __init__(self) -> None:
        self.run = AgentRun(
            id=uuid4(),
            thread_id="t1",
            work_id=None,
            experiment="assistant",
            goal="g",
            status="queued",
            state={},
            steps=0,
            tokens=0,
            cost=0.0,
            error=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def create(self, goal: str, work_id: UUID | None, experiment: str) -> AgentRun:
        return self.run

    async def get(self, run_id: UUID) -> AgentRun | None:
        return self.run

    async def save(self, run_id: UUID, **values: Any) -> AgentRun | None:
        self.run = replace(self.run, **values)
        return self.run

    async def decide(self, run_id: UUID, approval_id: UUID, decision: str) -> AgentRun | None:
        return self.run


async def test_cancel_agent_run() -> None:
    repo = FakeAgentRepository()
    service = AgentServiceImpl(repo)
    run = await service.cancel(repo.run.id)
    assert run.status == "cancelled"
