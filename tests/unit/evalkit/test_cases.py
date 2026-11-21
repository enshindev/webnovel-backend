from __future__ import annotations

from pathlib import Path

import pytest

from webnovel.evalkit.cases import load_cases

ROOT = Path(__file__).resolve().parents[3]


def test_loads_smoke_cases_from_real_evals() -> None:
    cases = load_cases(ROOT / "evals", suite="smoke")
    assert len(cases) == 19
    assert all("smoke" in case.spec.tags for case in cases)
    assert len({case.spec.id for case in cases}) == 19


def test_full_suite_includes_everything() -> None:
    cases = load_cases(ROOT / "evals", suite="full")
    assert len(cases) == 29


def test_rejects_duplicate_ids(tmp_path: Path) -> None:
    task = tmp_path / "generation" / "continuation"
    task.mkdir(parents=True)
    row = '{"id":"dup","input":{},"tags":["smoke"]}\n'
    (task / "cases.jsonl").write_text(row + row, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case id"):
        load_cases(tmp_path, suite="smoke")
