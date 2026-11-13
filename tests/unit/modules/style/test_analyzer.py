from __future__ import annotations

from webnovel.modules.style.analyzer import compare_features, extract_features


def test_extract_features() -> None:
    features = extract_features("“走。”他说。\n\n雨很大。")
    assert features["sentence_count"] >= 2
    assert 0 <= features["dialogue_ratio"] <= 1


def test_compare_features_returns_score_and_issues() -> None:
    profile = extract_features("短句。短句。")
    score, dimensions, issues = compare_features(profile, "这是一个非常非常长的句子，" * 20)
    assert 0 <= score <= 100
    assert dimensions
    assert issues
