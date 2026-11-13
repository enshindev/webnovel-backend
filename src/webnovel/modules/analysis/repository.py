from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.analysis.contract import AnalysisRun, OutlineDraft
from webnovel.modules.analysis.models import (
    AnalysisRunModel,
    ChapterAnalysisModel,
    OutlineDraftModel,
)


class AnalysisRepository(Protocol):
    async def create_run(self, work_id: UUID, params: dict[str, Any]) -> AnalysisRun: ...

    async def get_run(self, run_id: UUID) -> AnalysisRun | None: ...

    async def list_runs(self, work_id: UUID, limit: int) -> list[AnalysisRun]: ...

    async def set_status(
        self,
        run_id: UUID,
        status: str,
        report: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None: ...

    async def add_chapter(self, run_id: UUID, data: dict[str, Any]) -> None: ...

    async def get_outline(self, run_id: UUID) -> OutlineDraft | None: ...

    async def save_outline(
        self, run_id: UUID, work_id: UUID, content: dict[str, Any]
    ) -> OutlineDraft: ...

    async def update_outline(
        self, run_id: UUID, content: dict[str, Any], status: str | None
    ) -> OutlineDraft | None: ...


def _run(model: AnalysisRunModel) -> AnalysisRun:
    return AnalysisRun(
        id=model.id,
        work_id=model.work_id,
        kind=model.kind,
        status=model.status,
        params=model.params,
        report=model.report,
        error=model.error,
        created_at=model.created_at,
    )


class SqlAlchemyAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(self, work_id: UUID, params: dict[str, Any]) -> AnalysisRun:
        model = AnalysisRunModel(work_id=work_id, params=params)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _run(model)

    async def get_run(self, run_id: UUID) -> AnalysisRun | None:
        model = await self._session.get(AnalysisRunModel, run_id)
        return _run(model) if model is not None else None

    async def list_runs(self, work_id: UUID, limit: int) -> list[AnalysisRun]:
        rows = (
            (
                await self._session.execute(
                    select(AnalysisRunModel)
                    .where(AnalysisRunModel.work_id == work_id)
                    .order_by(AnalysisRunModel.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [_run(row) for row in rows]

    async def set_status(
        self,
        run_id: UUID,
        status: str,
        report: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        model = await self._session.get(AnalysisRunModel, run_id)
        if model is None:
            return
        model.status = status
        if report is not None:
            model.report = report
        if error is not None:
            model.error = error
        if status in {"ready", "failed"}:
            from datetime import UTC, datetime

            model.finished_at = datetime.now(UTC)
        await self._session.flush()

    async def add_chapter(self, run_id: UUID, data: dict[str, Any]) -> None:
        self._session.add(ChapterAnalysisModel(run_id=run_id, **data))
        await self._session.flush()

    async def get_outline(self, run_id: UUID) -> OutlineDraft | None:
        row = (
            await self._session.execute(
                select(OutlineDraftModel)
                .where(OutlineDraftModel.analysis_run_id == run_id)
                .order_by(OutlineDraftModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return OutlineDraft(row.id, row.work_id, row.analysis_run_id, row.status, row.content)

    async def update_outline(
        self, run_id: UUID, content: dict[str, Any], status: str | None
    ) -> OutlineDraft | None:
        row = (
            await self._session.execute(
                select(OutlineDraftModel)
                .where(OutlineDraftModel.analysis_run_id == run_id)
                .order_by(OutlineDraftModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.content = content
        if status is not None:
            row.status = status
        await self._session.flush()
        await self._session.refresh(row)
        return OutlineDraft(row.id, row.work_id, row.analysis_run_id, row.status, row.content)

    async def save_outline(
        self, run_id: UUID, work_id: UUID, content: dict[str, Any]
    ) -> OutlineDraft:
        row = OutlineDraftModel(
            work_id=work_id, analysis_run_id=run_id, status="draft", content=content
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return OutlineDraft(row.id, row.work_id, row.analysis_run_id, row.status, row.content)
