from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from webnovel.evalkit.schema import EvalCaseSpec


@dataclass(frozen=True, slots=True)
class LoadedCase:
    spec: EvalCaseSpec
    module: str
    task: str
    path: Path


def load_cases(root: Path, suite: str = "smoke") -> list[LoadedCase]:
    cases: list[LoadedCase] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("cases.jsonl")):
        module, task = path.parent.parent.name, path.parent.name
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                spec = EvalCaseSpec.model_validate(json.loads(line))
            except Exception as exc:
                raise ValueError(f"{path}:{line_number}: invalid eval case: {exc}") from exc
            if suite != "full" and suite not in spec.tags:
                continue
            if spec.id in seen:
                raise ValueError(f"{path}:{line_number}: duplicate case id {spec.id!r}")
            seen.add(spec.id)
            cases.append(LoadedCase(spec=spec, module=module, task=task, path=path))
    return cases
