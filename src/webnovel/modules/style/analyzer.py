from __future__ import annotations

import re
from collections import Counter
from typing import Any

_SENTENCE = re.compile(r"[。！？!?]+")
_WORD = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z]+")


def extract_features(text: str) -> dict[str, Any]:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    sentences = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    words = _WORD.findall(text)
    word_count = max(1, len(words))
    sentence_lengths = [len(sentence) for sentence in sentences]
    dialogue_count = sum(1 for paragraph in paragraphs if "“" in paragraph)
    unique = len(set(words))
    return {
        "word_count": word_count,
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "avg_sentence_length": round(sum(sentence_lengths) / max(1, len(sentence_lengths)), 2),
        "max_sentence_length": max(sentence_lengths, default=0),
        "dialogue_ratio": round(dialogue_count / max(1, len(paragraphs)), 3),
        "ellipsis_per_1000": round(text.count("……") / word_count * 1_000, 2),
        "dash_per_1000": round(text.count("——") / word_count * 1_000, 2),
        "exclamation_per_1000": round(text.count("！") / word_count * 1_000, 2),
        "vocabulary_richness": round(unique / word_count, 3),
        "top_words": [word for word, _ in Counter(words).most_common(10)],
    }


def compare_features(
    profile: dict[str, Any], text: str
) -> tuple[float, dict[str, Any], list[dict[str, Any]]]:
    current = extract_features(text)
    dimensions = {
        "sentence_length": _delta(
            float(profile.get("avg_sentence_length", 0)),
            float(current["avg_sentence_length"]),
            20,
        ),
        "dialogue_ratio": _delta(
            float(profile.get("dialogue_ratio", 0)),
            float(current["dialogue_ratio"]),
            0.25,
        ),
        "paragraph_length": _delta(
            float(profile.get("paragraph_count", 0)),
            float(current["paragraph_count"]),
            10,
        ),
        "vocabulary_richness": _delta(
            float(profile.get("vocabulary_richness", 0)),
            float(current["vocabulary_richness"]),
            0.2,
        ),
    }
    issues: list[dict[str, Any]] = []
    for name, score in dimensions.items():
        if score < 0.6:
            issues.append(
                {
                    "dimension": name,
                    "severity": "P1" if score < 0.4 else "P2",
                    "message": f"{name} 与声纹偏差较大（{score:.2f}）",
                }
            )
    score = round(sum(dimensions.values()) / len(dimensions) * 100, 1)
    return score, dimensions, issues


def _delta(expected: float, actual: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 1.0
    return max(0.0, min(1.0, 1 - abs(expected - actual) / tolerance))
