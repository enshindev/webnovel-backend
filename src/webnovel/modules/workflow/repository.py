from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.workflow.contract import WorkflowRun
from webnovel.modules.workflow.models import WorkflowRunModel


class WorkflowRepository(Protocol):
    async def create(self, work_id: UUID, template: str, stages: list[str]) -> WorkflowRun: ...

    async def get(self, run_id: UUID) -> WorkflowRun | None: ...

    async def claim(self, run_id: UUID) -> WorkflowRun | None: ...

    async def list(self, work_id: UUID) -> list[WorkflowRun]: ...

    async def save(self, run_id: UUID, **values: Any) -> WorkflowRun | None: ...


def _domain(model: WorkflowRunModel) -> WorkflowRun:
    return WorkflowRun(
        id=model.id,
        work_id=model.work_id,
        template=model.template,
        status=model.status,
        current_stage=model.current_stage,
        stages=list(model.stages),
        artifacts=dict(model.artifacts),
        error=model.error,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, work_id: UUID, template: str, stages: list[str]) -> WorkflowRun:
        model = WorkflowRunModel(
            work_id=work_id,
            template=template,
            status="waiting_confirmation",
            current_stage=stages[0],
            stages=stages,
            artifacts={},
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _domain(model)

    async def get(self, run_id: UUID) -> WorkflowRun | None:
        model = await self._session.get(WorkflowRunModel, run_id)
        return _domain(model) if model is not None else None

    async def claim(self, run_id: UUID) -> WorkflowRun | None:
        model = (
            await self._session.execute(
                select(WorkflowRunModel)
                .where(
                    WorkflowRunModel.id == run_id,
                    WorkflowRunModel.status == "waiting_confirmation",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        model.status = "executing"
        await self._session.flush()
        await self._session.refresh(model)
        return _domain(model)

    async def list(self, work_id: UUID) -> list[WorkflowRun]:
        rows = (
            (
                await self._session.execute(
                    select(WorkflowRunModel)
                    .where(WorkflowRunModel.work_id == work_id)
                    .order_by(WorkflowRunModel.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [_domain(row) for row in rows]

    async def save(self, run_id: UUID, **values: Any) -> WorkflowRun | None:
        model = await self._session.get(WorkflowRunModel, run_id)
        if model is None:
            return None
        for key, value in values.items():
            setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return _domain(model)
