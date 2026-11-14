from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from webnovel.modules.prompts.promotion import promote_label


def _prompt(root: Path) -> None:
    task = root / "generation" / "continuation"
    task.mkdir(parents=True)
    (task / "v001.yaml").write_text(
        "id: generation/continuation\nversion: 1\ntemplate: old\n", encoding="utf-8"
    )
    (task / "v002.yaml").write_text(
        "id: generation/continuation\nversion: 2\ntemplate: new\n", encoding="utf-8"
    )
    (task / "labels.yaml").write_text("labels:\n  production: 1\n  staging: 1\n", encoding="utf-8")


def test_promote_label_moves_only_target_label(tmp_path: Path) -> None:
    _prompt(tmp_path)
    previous = promote_label(tmp_path, "generation/continuation", 2)
    assert previous == 1
    data = yaml.safe_load(
        (tmp_path / "generation" / "continuation" / "labels.yaml").read_text(encoding="utf-8")
    )
    assert data["labels"] == {"production": 2, "staging": 1}


def test_promote_label_rejects_missing_version(tmp_path: Path) -> None:
    _prompt(tmp_path)
    with pytest.raises(FileNotFoundError):
        promote_label(tmp_path, "generation/continuation", 9)


def test_promote_label_creates_labels_file(tmp_path: Path) -> None:
    task = tmp_path / "generation" / "continuation"
    task.mkdir(parents=True)
    (task / "v001.yaml").write_text(
        "id: generation/continuation\nversion: 1\ntemplate: old\n", encoding="utf-8"
    )
    promote_label(tmp_path, "generation/continuation", 1)
    data = yaml.safe_load((task / "labels.yaml").read_text(encoding="utf-8"))
    assert data["labels"] == {"production": 1}
