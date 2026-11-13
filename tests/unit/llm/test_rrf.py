from __future__ import annotations

from webnovel.llm.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_merges_two_rankings() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
    ids = [doc_id for doc_id, _ in fused]
    assert ids[:2] == ["a", "b"]
    assert "d" in ids


def test_rrf_prefers_document_in_both_lists() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]]))
    assert fused["b"] > fused["a"]
    assert fused["b"] > fused["c"]
