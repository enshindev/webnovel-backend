from __future__ import annotations

from typing import Any


def summarize(results: list[dict[str, Any]], must_pass_ids: set[str]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.get("passed"))
    passed_ids = {str(result["case_id"]) for result in results if result.get("passed")}
    must_pass_total = len(must_pass_ids)
    must_pass_passed = len(must_pass_ids & passed_ids)
    gate = "passed" if must_pass_passed == must_pass_total else "failed"
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "must_pass_total": must_pass_total,
        "must_pass_passed": must_pass_passed,
        "gate": gate,
    }
