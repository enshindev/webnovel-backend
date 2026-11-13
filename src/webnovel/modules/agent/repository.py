from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.agent.contract import AgentApproval, AgentRun
from webnovel.modules.agent.models import AgentApprovalModel, AgentRunModel


class AgentRepository(Protocol):
    async def create(self, goal: str, work_id: UUID | None, experiment: str) -> AgentRun: ...

    async def get(self, run_id: UUID) -> AgentRun | None: ...

    async def save(self, run_id: UUID, **values: Any) -> AgentRun | None: ...

    async def decide(self, run_id: UUID, approval_id: UUID, decision: str) -> AgentRun | None: ...

    async def add_approval(
        self, run_id: UUID, action: str, payload: dict[str, Any]
    ) -> AgentRun | None: ...


def _approval(model: AgentApprovalModel) -> AgentApproval:
    return AgentApproval(
        id=model.id,
        run_id=model.run_id,
        action=model.action,
        payload=model.payload,
        status=model.status,
        decided_at=model.decided_at,
        created_at=model.created_at,
    )


def _run(model: AgentRunModel, approvals: list[AgentApprovalModel]) -> AgentRun:
    return AgentRun(
        id=model.id,
        thread_id=model.thread_id,
        work_id=model.work_id,
        experiment=model.experiment,
        goal=model.goal,
        status=model.status,
        state=model.state,
        steps=model.steps,
        tokens=model.tokens,
        cost=float(model.cost),
        error=model.error,
        created_at=model.created_at,
        updated_at=model.updated_at,
        pending_approvals=[_approval(item) for item in approvals],
    )


class SqlAlchemyAgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, goal: str, work_id: UUID | None, experiment: str) -> AgentRun:
        model = AgentRunModel(
            thread_id=uuid4().hex,
            work_id=work_id,
            experiment=experiment,
            goal=goal,
            status="queued",
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _run(model, [])

    async def get(self, run_id: UUID) -> AgentRun | None:
        model = await self._session.get(AgentRunModel, run_id)
        if model is None:
            return None
        approvals = (
            (
                await self._session.execute(
                    select(AgentApprovalModel)
                    .where(AgentApprovalModel.run_id == run_id)
                    .order_by(AgentApprovalModel.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        return _run(model, list(approvals))

    async def save(self, run_id: UUID, **values: Any) -> AgentRun | None:
        model = await self._session.get(AgentRunModel, run_id)
        if model is None:
            return None
        for key, value in values.items():
            setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return await self.get(run_id)

    async def add_approval(
        self, run_id: UUID, action: str, payload: dict[str, Any]
    ) -> AgentRun | None:
        run = await self._session.get(AgentRunModel, run_id)
        if run is None:
            return None
        self._session.add(
            AgentApprovalModel(
                run_id=run_id,
                action=action,
                payload=payload,
                status="pending",
            )
        )
        run.status = "waiting_approval"
        await self._session.flush()
        await self._session.refresh(run)
        return await self.get(run_id)

    async def decide(self, run_id: UUID, approval_id: UUID, decision: str) -> AgentRun | None:
        run = await self._session.get(AgentRunModel, run_id)
        approval = await self._session.get(AgentApprovalModel, approval_id)
        if run is None or approval is None or approval.run_id != run_id:
            return None
        if approval.status != "pending":
            return None
        approval.status = "approved" if decision == "approve" else "rejected"
        from datetime import UTC, datetime

        approval.decided_at = datetime.now(UTC)
        remaining = (
            (
                await self._session.execute(
                    select(AgentApprovalModel).where(
                        AgentApprovalModel.run_id == run_id,
                        AgentApprovalModel.status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
        run.status = "waiting_approval" if remaining else "running"
        await self._session.flush()
        await self._session.refresh(run)
        return await self.get(run_id)
