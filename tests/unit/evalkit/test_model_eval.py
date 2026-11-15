from __future__ import annotations

from pathlib import Path
from typing import Any

from webnovel.evalkit.cases import LoadedCase
from webnovel.evalkit.model_eval import run_cases
from webnovel.evalkit.schema import EvalCaseSpec
from webnovel.llm.prompts.schema import PromptSpec


class FakeClient:
    def __init__(self, output: str = "", error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.requests: list[Any] = []

    async def complete(self, request: Any) -> str:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.output


def _case(case_id: str = "case-1") -> LoadedCase:
    spec = EvalCaseSpec(
        id=case_id,
        input={"chapter_text": "沈砚走进旧巷。"},
        expected_facts=["旧巷", "钟声"],
    )
    return LoadedCase(
        spec=spec,
        module="generation",
        task="continuation",
        path=Path("evals/generation/continuation/cases.jsonl"),
    )


def _prompt() -> PromptSpec:
    return PromptSpec(
        id="generation/continuation",
        version=1,
        template="续写：{{chapter_text}}",
        variables=["chapter_text"],
        defaults={"max_tokens": 100, "temperature": 0.5},
    )


async def test_run_cases_calls_model_and_judges_output() -> None:
    client = FakeClient("他走进旧巷，听见钟声。")
    results = await run_cases(
        [_case()],
        client=client,  # type: ignore[arg-type]
        model="fake",
        prompt=_prompt(),
        includes={},
    )
    assert results[0].result["passed"] is True
    assert results[0].output == "他走进旧巷，听见钟声。"
    assert client.requests[0].max_tokens == 100


async def test_run_cases_records_model_error() -> None:
    results = await run_cases(
        [_case()],
        client=FakeClient(error=RuntimeError("provider down")),  # type: ignore[arg-type]
        model="fake",
        prompt=_prompt(),
        includes={},
    )
    assert results[0].result["passed"] is False
    assert "provider down" in results[0].result["details"]["error"]
