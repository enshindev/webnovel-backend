from __future__ import annotations

import json
from typing import Any

from webnovel.evalkit.schema import EvalCaseSpec
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest


def judge_output(case: EvalCaseSpec, output: str) -> dict[str, Any]:
    """确定性检查：只核对 expected_facts 是否出现在输出里。"""
    normalized = output.casefold()
    facts = [fact.strip() for fact in case.expected_facts if fact.strip()]
    matched = [fact for fact in facts if fact.casefold() in normalized]
    missing = [fact for fact in facts if fact not in matched]
    passed = all(fact in matched for fact in facts) if facts else bool(output.strip())
    score = len(matched) / len(facts) if facts else (1.0 if passed else 0.0)
    return {
        "case_id": case.id,
        "passed": passed,
        "score": round(score, 4),
        "details": {
            "matched": matched,
            "missing": missing,
            "output_chars": len(output),
        },
    }


class LLMJudge:
    def __init__(self, client: ModelClient, model: str) -> None:
        self._client = client
        self._model = model

    async def judge(self, case: EvalCaseSpec, output: str) -> dict[str, Any]:
        prompt = (
            "你是网文编辑。请按 rubric 判断候选续写是否合格，只返回 JSON："
            '{"passed": true/false, "score": 0-1, "reason": "..."}。\n'
            f"rubric: {case.rubric}\n"
            f"expected_facts: {case.expected_facts}\n"
            f"constraints: {case.constraints}\n"
            f"candidate:\n{output}"
        )
        try:
            raw = await self._client.complete(
                ModelRequest(
                    model=self._model,
                    messages=[ChatMessage(role="user", content=prompt)],
                    temperature=0.0,
                    max_tokens=300,
                )
            )
            data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            passed = bool(data.get("passed"))
            score = float(data.get("score", 1.0 if passed else 0.0))
            return {
                "case_id": case.id,
                "passed": passed,
                "score": max(0.0, min(1.0, score)),
                "details": {"judge": "llm", "reason": str(data.get("reason", ""))},
            }
        except Exception as exc:
            fallback = judge_output(case, output)
            fallback["details"]["judge"] = "deterministic_fallback"
            fallback["details"]["judge_error"] = str(exc)
            return fallback
