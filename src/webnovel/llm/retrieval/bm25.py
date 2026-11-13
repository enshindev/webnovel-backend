from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

_TOKEN = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN.findall(text)]


class BM25Index:
    """轻量 BM25；用于与向量结果做 RRF 融合。"""

    def __init__(self, documents: Sequence[str], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._documents = list(documents)
        self._tokens = [tokenize(text) for text in documents]
        self._lengths = [len(tokens) for tokens in self._tokens]
        self._avg_length = sum(self._lengths) / max(1, len(self._lengths))
        self._k1 = k1
        self._b = b
        self._df: Counter[str] = Counter()
        for tokens in self._tokens:
            self._df.update(set(tokens))
        self._n = max(1, len(self._documents))

    def search(self, query: str, limit: int = 10) -> list[tuple[int, float]]:
        terms = tokenize(query)
        scores: list[tuple[int, float]] = []
        for index, tokens in enumerate(self._tokens):
            counts = Counter(tokens)
            score = 0.0
            for term in terms:
                frequency = counts[term]
                if frequency == 0:
                    continue
                df = self._df[term]
                idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
                denom = frequency + self._k1 * (
                    1 - self._b + self._b * self._lengths[index] / max(1.0, self._avg_length)
                )
                score += idf * frequency * (self._k1 + 1) / denom
            if score > 0:
                scores.append((index, score))
        scores.sort(key=lambda item: (-item[1], item[0]))
        return scores[:limit]
