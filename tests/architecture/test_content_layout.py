from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from webnovel.evalkit.schema import EvalCaseSpec
from webnovel.llm.prompts.schema import PromptSpec

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "webnovel"
PROMPTS = ROOT / "prompts"
EVALS = ROOT / "evals"
CONTENT_EXTRA = {"shared", "cross"}


def _module_names() -> set[str]:
    modules_dir = SRC / "modules"
    return {
        path.name
        for path in modules_dir.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }


def _top_level_dirs(root: Path) -> set[str]:
    return {path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")}


def _prompt_files() -> list[Path]:
    return sorted(PROMPTS.rglob("v*.yaml"))


def _eval_files() -> list[Path]:
    return sorted(EVALS.rglob("cases.jsonl"))


def test_prompt_top_level_dirs_are_modules_or_whitelisted() -> None:
    allowed = _module_names() | CONTENT_EXTRA
    assert _top_level_dirs(PROMPTS) <= allowed, (
        f"unexpected prompts dirs: {_top_level_dirs(PROMPTS) - allowed}"
    )


def test_eval_top_level_dirs_are_modules_or_whitelisted() -> None:
    allowed = _module_names() | CONTENT_EXTRA
    assert _top_level_dirs(EVALS) <= allowed, (
        f"unexpected evals dirs: {_top_level_dirs(EVALS) - allowed}"
    )


def test_prompt_schema_and_id_match_path() -> None:
    for path in _prompt_files():
        spec = PromptSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        relative = path.parent.relative_to(PROMPTS).as_posix()
        assert spec.id == relative, f"{path}: id {spec.id!r} != path {relative!r}"
        assert path.name == f"v{spec.version:03d}.yaml", f"{path}: version mismatch"


def test_prompt_versions_are_contiguous() -> None:
    for task_dir in {path.parent for path in _prompt_files()}:
        versions = sorted(int(path.stem.removeprefix("v")) for path in task_dir.glob("v*.yaml"))
        assert versions == list(range(1, max(versions) + 1)), f"{task_dir}: versions {versions}"


def test_prompt_includes_are_pinned_and_exist() -> None:
    for path in _prompt_files():
        spec = PromptSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        for include in spec.includes:
            target = PROMPTS / include.id / f"v{include.version:03d}.yaml"
            assert target.exists(), f"{path}: missing include {include.id}@v{include.version}"
            token = f"{{{{> {include.id}@v{include.version:03d}}}}}"
            assert token in spec.template, f"{path}: include not referenced in template: {token}"


def test_labels_reference_existing_versions() -> None:
    for labels_path in PROMPTS.rglob("labels.yaml"):
        data = yaml.safe_load(labels_path.read_text(encoding="utf-8")) or {}
        labels = data.get("labels", {})
        assert labels, f"{labels_path}: empty labels"
        for label, version in labels.items():
            assert isinstance(version, int) and version >= 1
            target = labels_path.parent / f"v{version:03d}.yaml"
            assert target.exists(), f"{labels_path}: {label} -> missing {target.name}"


def test_shared_prompts_have_no_labels() -> None:
    assert not list((PROMPTS / "shared").rglob("labels.yaml")), (
        "shared prompts are referenced by explicit @vNNN, not labels"
    )


def test_eval_case_ids_are_unique_and_validate_schema() -> None:
    seen: set[str] = set()
    for path in _eval_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            assert "prompt_version" not in raw, f"{raw.get('id')}: do not pin prompt version"
            assert "prompt_version" not in raw.get("input", {}), (
                f"{raw.get('id')}: do not pin prompt version"
            )
            case = EvalCaseSpec.model_validate(raw)
            case_id = case.id
            assert case_id not in seen, f"duplicate eval case id: {case_id}"
            seen.add(case_id)


def _published_prompt_paths() -> set[str]:
    published: set[str] = set()
    for labels_path in PROMPTS.rglob("labels.yaml"):
        data = yaml.safe_load(labels_path.read_text(encoding="utf-8")) or {}
        for version in data.get("labels", {}).values():
            path = labels_path.parent / f"v{version:03d}.yaml"
            published.add(path.relative_to(ROOT).as_posix())

    # 已发布 prompt 引用到的共享片段也视为已发布，避免改 shared/ 悄悄影响任务。
    changed = True
    while changed:
        changed = False
        for path in _prompt_files():
            rel = path.relative_to(ROOT).as_posix()
            if rel not in published:
                continue
            spec = PromptSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            for include in spec.includes:
                target = PROMPTS / include.id / f"v{include.version:03d}.yaml"
                target_rel = target.relative_to(ROOT).as_posix()
                if target_rel not in published:
                    published.add(target_rel)
                    changed = True
    return published


def test_published_prompt_files_are_not_modified() -> None:
    if shutil.which("git") is None:
        pytest.skip("git not available")
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if inside.returncode != 0:
        pytest.skip("not a git worktree")

    published = _published_prompt_paths()
    base = os.environ.get("GIT_BASE_REF")
    if base:
        diff_args = ["git", "diff", "--name-status", f"{base}...HEAD", "--", "prompts"]
    else:
        diff_args = ["git", "diff", "--name-status", "HEAD", "--", "prompts"]

    changed: set[str] = set()
    for line in subprocess.run(
        diff_args, cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines():
        parts = line.split("\t")
        status = parts[0][:1]
        if status in {"M", "D"} and len(parts) >= 2:
            changed.add(parts[1])
        elif status == "R" and len(parts) >= 3:
            changed.update({parts[1], parts[2]})

    modified_published = sorted(changed & published)
    assert not modified_published, (
        "published prompt versions are immutable; add a new vNNN instead: "
        + ", ".join(modified_published)
    )
