from __future__ import annotations

from typing import Any
from uuid import UUID

from webnovel.modules.quality.eval_repository import EvalRepository


class EvalService:
    def __init__(self, repository: EvalRepository) -> None:
        self._repository = repository

    async def run(
        self,
        *,
        task: str,
        cases: list[dict[str, Any]],
        prompt_name: str | None = None,
        prompt_version: int | None = None,
        model: str | None = None,
        params: dict[str, Any] | None = None,
        results: list[dict[str, Any]] | None = None,
    ) -> tuple[UUID, dict[str, Any]]:
        must_pass_ids = {str(case["id"]) for case in cases if case.get("must_pass")}
        run_id = await self._repository.create_run(
            task, prompt_name, prompt_version, model, params or {}
        )
        if results is None:
            metrics = {
                "total": len(cases),
                "must_pass_total": len(must_pass_ids),
                "mode": "inventory",
            }
            await self._repository.finish_run(
                run_id, status="prepared", metrics=metrics, results=[]
            )
            return run_id, metrics

        passed_ids = {str(result["case_id"]) for result in results if result.get("passed")}
        passed = len(passed_ids)
        must_pass_passed = len(must_pass_ids & passed_ids)
        metrics = {
            "total": len(results),
            "passed": passed,
            "pass_rate": round(passed / len(results), 4) if results else 0.0,
            "must_pass_total": len(must_pass_ids),
            "must_pass_passed": must_pass_passed,
            "gate": "passed" if must_pass_passed == len(must_pass_ids) else "failed",
        }
        await self._repository.finish_run(
            run_id, status="succeeded", metrics=metrics, results=results
        )
        return run_id, metrics
