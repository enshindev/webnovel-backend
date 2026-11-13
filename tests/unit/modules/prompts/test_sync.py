from __future__ import annotations

from pathlib import Path

from webnovel.modules.prompts.service import PromptCatalogService


class FakeRepository:
    def __init__(self) -> None:
        self.versions: list[dict[str, object]] = []
        self.labels: list[tuple[str, str, int]] = []

    async def upsert_version(self, values: dict[str, object]) -> None:
        self.versions.append(values)

    async def upsert_label(self, prompt_id: str, label: str, version: int) -> None:
        self.labels.append((prompt_id, label, version))

    async def versions(self, prompt_id: str):
        return []


async def test_prompt_catalog_sync(tmp_path: Path) -> None:
    task = tmp_path / "demo" / "task"
    task.mkdir(parents=True)
    (task / "v001.yaml").write_text(
        "id: demo/task\nversion: 1\nvariables: [text]\ntemplate: '{{text}}'\n"
    )
    (task / "labels.yaml").write_text("labels:\n  production: 1\n")
    repo = FakeRepository()
    counts = await PromptCatalogService(repo).sync(tmp_path)  # type: ignore[arg-type]
    assert counts == {"versions": 1, "labels": 1}
    assert repo.versions[0]["prompt_id"] == "demo/task"
    assert repo.labels == [("demo/task", "production", 1)]
