from __future__ import annotations

from pathlib import Path

from webnovel.modules.assistant.knowledge import KnowledgeRetriever


def test_search_markdown_knowledge(tmp_path: Path) -> None:
    (tmp_path / "craft").mkdir()
    (tmp_path / "craft" / "hooks.md").write_text(
        "# 钩子\n\n开篇钩子要在前三段制造具体危险。\n\n另一种钩子是信息差。",
        encoding="utf-8",
    )
    retriever = KnowledgeRetriever(tmp_path)
    hits = retriever.search("开篇钩子")
    assert hits
    assert "钩子" in hits[0].text


class FakeEmbeddingClient:
    dimensions = 2

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "钩子" in text else [0.0, 1.0] for text in texts]


async def test_async_vector_search(tmp_path: Path) -> None:
    (tmp_path / "craft").mkdir()
    (tmp_path / "craft" / "hooks.md").write_text(
        "开篇钩子要在前三段制造具体危险。\n\n无关内容。", encoding="utf-8"
    )
    retriever = KnowledgeRetriever(tmp_path, FakeEmbeddingClient())
    hits = await retriever.asearch("开篇钩子")
    assert hits
    assert "钩子" in hits[0].text


class FakeKnowledgeRepository:
    def __init__(self) -> None:
        self.rows: list[tuple[object, ...]] = []

    async def replace_all(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    async def search(self, embedding: list[float], limit: int):
        from webnovel.modules.assistant.knowledge_types import KnowledgeChunk

        return [KnowledgeChunk("craft/hooks.md", "hooks:0", "钩子", 90)]


class FakeKnowledgeClient:
    dimensions = 2

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


async def test_knowledge_index_and_search(tmp_path: Path) -> None:
    from webnovel.modules.assistant.knowledge import KnowledgeIndexer, KnowledgeSearchService

    repo = FakeKnowledgeRepository()
    client = FakeKnowledgeClient()
    indexer = KnowledgeIndexer(client, repo)
    count = await indexer.index(KnowledgeRetriever(tmp_path))
    assert count == 0
    service = KnowledgeSearchService(client, repo)
    hits = await service.search("钩子")
    assert hits[0].ref == "hooks:0"
