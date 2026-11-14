from __future__ import annotations

from typing import Any

from webnovel.evalkit.schema import EvalCaseSpec


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
