from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from webnovel.modules.quality.eval_service import EvalService


class FakeEvalRepository:
    def __init__(self) -> None:
        self.run_id = uuid4()
        self.finished: dict[str, Any] | None = None

    async def create_run(
        self,
        task: str,
        prompt_name: str | None,
        prompt_version: int | None,
        model: str | None,
        params: dict[str, Any],
    ) -> UUID:
        return self.run_id

    async def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        metrics: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> None:
        self.finished = {"status": status, "metrics": metrics, "results": results}


async def test_eval_service_records_results() -> None:
    repo = FakeEvalRepository()
    run_id = await EvalService(repo).run(task="smoke", cases=[{"id": "case-1"}])
    assert run_id == repo.run_id
    assert repo.finished is not None
    assert repo.finished["metrics"]["passed"] == 1
