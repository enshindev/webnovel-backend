from __future__ import annotations

from webnovel.evalkit.judge import judge_output
from webnovel.evalkit.schema import EvalCaseSpec
from webnovel.evalkit.summary import summarize


def _case(must_pass: bool = True) -> EvalCaseSpec:
    return EvalCaseSpec(
        id="case-1",
        input={},
        expected_facts=["旧巷", "钟声"],
        must_pass=must_pass,
    )


def test_judge_passes_when_all_facts_present() -> None:
    result = judge_output(_case(), "他走进旧巷，听见钟声。")
    assert result["passed"] is True
    assert result["score"] == 1.0


def test_judge_fails_and_reports_missing_facts() -> None:
    result = judge_output(_case(), "他走进旧巷。")
    assert result["passed"] is False
    assert result["details"]["missing"] == ["钟声"]


def test_summary_gate_requires_all_must_pass() -> None:
    results = [
        {"case_id": "case-1", "passed": True},
        {"case_id": "case-2", "passed": False},
    ]
    summary = summarize(results, {"case-1", "case-2"})
    assert summary["passed"] == 1
    assert summary["gate"] == "failed"
    assert summary["must_pass_passed"] == 1
