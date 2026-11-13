from __future__ import annotations

from pathlib import Path

import yaml

from webnovel.llm.prompts.schema import PromptSpec


class PromptRegistry:
    """只接收已解析的 prompts 根目录；不读环境变量、不拼相对路径。"""

    def __init__(self, root: Path) -> None:
        self._root = root

    def resolve(self, prompt_id: str, label: str = "production") -> PromptSpec:
        task_dir = self._root / prompt_id
        if not task_dir.is_dir():
            raise FileNotFoundError(f"prompt dir not found: {prompt_id}")

        version = self._label_version(task_dir, label)
        return self.load_version(prompt_id, version)

    def load_version(self, prompt_id: str, version: int) -> PromptSpec:
        path = self._root / prompt_id / f"v{version:03d}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"prompt version not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        spec = PromptSpec.model_validate(data)
        if spec.id != prompt_id:
            raise ValueError(f"prompt id mismatch: {spec.id} != {prompt_id}")
        return spec

    def load_includes(self, spec: PromptSpec) -> dict[str, PromptSpec]:
        """按 include 锁定的版本加载共享片段；键形如 shared/style@v001。"""
        return {
            f"{include.id}@v{include.version:03d}": self.load_version(include.id, include.version)
            for include in spec.includes
        }

    def _label_version(self, task_dir: Path, label: str) -> int:
        labels_path = task_dir / "labels.yaml"
        if labels_path.exists():
            data = yaml.safe_load(labels_path.read_text(encoding="utf-8")) or {}
            labels = data.get("labels", {})
            if label in labels:
                return int(labels[label])
        versions = sorted(task_dir.glob("v*.yaml"))
        if not versions:
            raise FileNotFoundError(f"no prompt versions in {task_dir}")
        return int(versions[-1].stem.removeprefix("v"))
