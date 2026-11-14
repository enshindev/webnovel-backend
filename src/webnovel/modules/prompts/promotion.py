from __future__ import annotations

from pathlib import Path

import yaml


def promote_label(
    root: Path, prompt_id: str, version: int, label: str = "production"
) -> int | None:
    """把 labels.yaml 里的 label 指向新版本，返回原版本。"""
    if version < 1:
        raise ValueError("version must be positive")
    if not label.strip():
        raise ValueError("label must not be empty")
    task_dir = root / prompt_id
    version_path = task_dir / f"v{version:03d}.yaml"
    if not version_path.is_file():
        raise FileNotFoundError(f"prompt version not found: {version_path}")

    labels_path = task_dir / "labels.yaml"
    data = (
        yaml.safe_load(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}
    ) or {}
    labels = dict(data.get("labels") or {})
    previous = labels.get(label)
    labels[label] = version
    data["labels"] = labels

    tmp_path = labels_path.with_suffix(".yaml.tmp")
    tmp_path.write_text(yaml.safe_dump(data, sort_keys=True, allow_unicode=True), encoding="utf-8")
    tmp_path.replace(labels_path)
    return int(previous) if previous is not None else None
