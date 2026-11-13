from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.quality.models import EvalCaseResultModel, EvalRunModel


class EvalRepository(Protocol):
    async def create_run(
        self,
        task: str,
        prompt_name: str | None,
        prompt_version: int | None,
        model: str | None,
        params: dict[str, Any],
    ) -> UUID: ...

    async def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        metrics: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> None: ...


class SqlAlchemyEvalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        task: str,
        prompt_name: str | None,
        prompt_version: int | None,
        model: str | None,
        params: dict[str, Any],
    ) -> UUID:
        model_row = EvalRunModel(
            task=task,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            model=model,
            params=params,
            status="running",
        )
        self._session.add(model_row)
        await self._session.flush()
        return model_row.id

    async def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        metrics: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> None:
        run = await self._session.get(EvalRunModel, run_id)
        if run is None:
            return
        run.status = status
        run.metrics = metrics
        run.finished_at = datetime.now(UTC)
        for result in results:
            self._session.add(
                EvalCaseResultModel(
                    run_id=run_id,
                    case_id=str(result["case_id"]),
                    passed=bool(result.get("passed", False)),
                    score=result.get("score"),
                    details=result.get("details", {}),
                )
            )
        await self._session.flush()
