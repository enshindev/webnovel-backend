from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.modules.prompts.repository import PromptCatalogRepository


class PromptCatalogService:
    def __init__(self, repository: PromptCatalogRepository) -> None:
        self._repository = repository

    async def sync(self, root: Path) -> dict[str, int]:
        registry = PromptRegistry(root)
        versions = 0
        labels = 0
        for task_dir in sorted(path for path in root.rglob("*") if path.is_dir()):
            prompt_id = task_dir.relative_to(root).as_posix()
            files = sorted(task_dir.glob("v*.yaml"))
            if not files:
                continue
            for path in files:
                spec = registry.load_version(prompt_id, int(path.stem.removeprefix("v")))
                raw = path.read_text(encoding="utf-8")
                await self._repository.upsert_version(
                    {
                        "prompt_id": spec.id,
                        "version": spec.version,
                        "template": spec.template,
                        "variables": spec.variables,
                        "defaults": spec.defaults,
                        "includes": [item.model_dump() for item in spec.includes],
                        "content_hash": hashlib.sha256(raw.encode()).hexdigest(),
                    }
                )
                versions += 1
            labels_path = task_dir / "labels.yaml"
            if labels_path.exists():
                data = yaml.safe_load(labels_path.read_text(encoding="utf-8")) or {}
                for label, version in (data.get("labels") or {}).items():
                    await self._repository.upsert_label(prompt_id, str(label), int(version))
                    labels += 1
        return {"versions": versions, "labels": labels}
