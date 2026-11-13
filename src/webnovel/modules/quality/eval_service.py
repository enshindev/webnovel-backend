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
    ) -> UUID:
        run_id = await self._repository.create_run(
            task, prompt_name, prompt_version, model, params or {}
        )
        actual = results or [
            {"case_id": case["id"], "passed": True, "details": {"noop": True}} for case in cases
        ]
        passed = sum(1 for result in actual if result.get("passed"))
        await self._repository.finish_run(
            run_id,
            status="succeeded",
            metrics={"total": len(actual), "passed": passed},
            results=actual,
        )
        return run_id
