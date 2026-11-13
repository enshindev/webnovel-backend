from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    task: str
    input: dict[str, Any]
    expected: dict[str, Any]
    must_pass: bool = False


@dataclass(frozen=True, slots=True)
class EvalRunMeta:
    prompt_id: str
    prompt_version: int
    case_set_hash: str
    model: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvalResult:
    case_id: str
    passed: bool
    score: float | None = None
    details: dict[str, Any] | None = None


class Judge(Protocol):
    async def score(self, case: EvalCase, output: str) -> EvalResult: ...


class NoopJudge:
    async def score(self, case: EvalCase, output: str) -> EvalResult:
        _ = output
        return EvalResult(case_id=case.id, passed=True)


class EvalHarness(Protocol):
    async def run(self, cases: list[EvalCase], meta: EvalRunMeta) -> list[EvalResult]: ...


class NoopEvalHarness:
    async def run(self, cases: list[EvalCase], meta: EvalRunMeta) -> list[EvalResult]:
        _ = meta
        return [EvalResult(case_id=case.id, passed=True) for case in cases]
