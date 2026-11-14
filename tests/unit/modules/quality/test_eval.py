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


async def test_eval_service_records_inventory_without_results() -> None:
    repo = FakeEvalRepository()
    run_id, metrics = await EvalService(repo).run(
        task="smoke", cases=[{"id": "case-1", "must_pass": True}]
    )
    assert run_id == repo.run_id
    assert repo.finished is not None
    assert repo.finished["status"] == "prepared"
    assert metrics["total"] == 1
    assert repo.finished["results"] == []


async def test_eval_service_computes_must_pass_gate() -> None:
    repo = FakeEvalRepository()
    _, metrics = await EvalService(repo).run(
        task="smoke",
        cases=[{"id": "case-1", "must_pass": True}, {"id": "case-2", "must_pass": False}],
        results=[
            {"case_id": "case-1", "passed": True},
            {"case_id": "case-2", "passed": False},
        ],
    )
    assert metrics["passed"] == 1
    assert metrics["must_pass_passed"] == 1
    assert metrics["gate"] == "passed"
    assert repo.finished is not None
    assert repo.finished["status"] == "succeeded"
