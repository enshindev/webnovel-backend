from __future__ import annotations

from webnovel.llm.retrieval.bm25 import BM25Index


def test_bm25_ranks_matching_document() -> None:
    index = BM25Index(["雨夜追捕", "晴天散步", "雨夜灯灭"])
    results = index.search("雨夜", limit=2)
    assert results
    assert results[0][0] in {0, 2}
