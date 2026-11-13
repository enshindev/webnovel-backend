from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from webnovel.infra.config import Settings
from webnovel.modules.agent.contract import AgentRun
from webnovel.modules.agent.executor import AgentExecutor


class FakeAgentRepository:
    def __init__(self) -> None:
        self.approvals: list[tuple[str, dict[str, Any]]] = []
        self.run = AgentRun(
            id=uuid4(),
            thread_id="t1",
            work_id=None,
            experiment="assistant",
            goal="整理开篇钩子",
            status="queued",
            state={},
            steps=0,
            tokens=0,
            cost=0.0,
            error=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def get(self, run_id: UUID) -> AgentRun | None:
        return self.run

    async def save(self, run_id: UUID, **values: Any) -> AgentRun | None:
        self.run = replace(self.run, **values)
        return self.run

    async def add_approval(
        self, run_id: UUID, action: str, payload: dict[str, Any]
    ) -> AgentRun | None:
        self.approvals.append((action, payload))
        self.run = replace(self.run, status="waiting_approval")
        return self.run


class FakeModel:
    async def complete(self, request: Any) -> str:
        return "三个开篇钩子"


async def test_agent_executor_runs_goal() -> None:
    repo = FakeAgentRepository()
    executor = AgentExecutor(
        repository=repo,
        model_client=FakeModel(),
        settings=Settings(),
    )
    await executor.run(repo.run.id)
    assert repo.run.status == "succeeded"
    assert repo.run.state["result"] == "三个开篇钩子"
    assert repo.run.steps == 1


class ApprovalModel:
    async def complete(self, request: Any) -> str:
        return (
            '{"final":false,"result":"准备改设定",'
            '"approval":{"action":"entity.update","payload":{"name":"沈砚"}}}'
        )


async def test_agent_executor_waits_for_approval() -> None:
    repo = FakeAgentRepository()
    executor = AgentExecutor(
        repository=repo,
        model_client=ApprovalModel(),
        settings=Settings(),
    )
    await executor.run(repo.run.id)
    assert repo.run.status == "waiting_approval"
    assert repo.approvals[0][0] == "entity.update"
