from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from webnovel.evalkit.cases import LoadedCase
from webnovel.evalkit.judge import judge_output
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.prompts.schema import PromptSpec


@dataclass(frozen=True, slots=True)
class ModelEvalResult:
    case_id: str
    output: str
    result: dict[str, Any]


async def run_cases(
    cases: Sequence[LoadedCase],
    *,
    client: ModelClient,
    model: str,
    prompt: PromptSpec,
    includes: Mapping[str, PromptSpec],
    limit: int | None = None,
    progress: Callable[[int, int, str], None] | None = None,
    judge: Callable[[Any, str], Awaitable[dict[str, Any]]] | None = None,
) -> list[ModelEvalResult]:
    selected = list(cases[:limit] if limit is not None else cases)
    results: list[ModelEvalResult] = []
    for index, case in enumerate(selected, 1):
        if progress is not None:
            progress(index, len(selected), case.spec.id)
        values = _values(case, prompt)
        output = ""
        started = time.monotonic()
        try:
            rendered = render_prompt(prompt, values, includes)
            output = await client.complete(
                ModelRequest(
                    model=model,
                    messages=[ChatMessage(role="user", content=rendered)],
                    temperature=float(prompt.defaults.get("temperature", 0.8)),
                    max_tokens=int(prompt.defaults.get("max_tokens", 1200)),
                )
            )
            result = (
                await judge(case.spec, output)
                if judge is not None
                else judge_output(case.spec, output)
            )
            result["details"]["latency_ms"] = round((time.monotonic() - started) * 1000)
        except Exception as exc:
            result = {
                "case_id": case.spec.id,
                "passed": False,
                "score": 0.0,
                "details": {"error": str(exc)},
            }
        results.append(ModelEvalResult(case_id=case.spec.id, output=output, result=result))
    return results


def _values(case: LoadedCase, prompt: PromptSpec) -> dict[str, str]:
    values = {name: str(case.spec.input.get(name, "")) for name in prompt.variables}
    if "instruction" in values and not values["instruction"]:
        values["instruction"] = "续写本章，承接上文，不自动推进大剧情。"
    return values
