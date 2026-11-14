from __future__ import annotations

from typing import Any

from webnovel.llm import usage


class FakeEncoder:
    def __init__(self) -> None:
        self.calls = 0

    def encode(self, text: str) -> list[str]:
        self.calls += 1
        return list(text)


class BrokenEncoder:
    def encode(self, text: str) -> list[str]:
        raise RuntimeError("encoding failed")


def test_encoder_is_loaded_lazily_and_cached(monkeypatch: Any) -> None:
    calls: list[str] = []
    encoder = FakeEncoder()

    def fake_get_encoding(name: str) -> FakeEncoder:
        calls.append(name)
        return encoder

    usage._get_encoder.cache_clear()
    monkeypatch.setattr(usage.tiktoken, "get_encoding", fake_get_encoding)

    assert calls == []
    assert usage.estimate_tokens("长夜") == 2
    assert usage.estimate_tokens("灯火") == 2
    assert calls == ["cl100k_base"]
    assert encoder.calls == 2
    usage._get_encoder.cache_clear()


def test_falls_back_to_character_count_when_encoder_is_unavailable(
    monkeypatch: Any,
) -> None:
    def fail(_: str) -> None:
        raise RuntimeError("offline")

    usage._get_encoder.cache_clear()
    monkeypatch.setattr(usage.tiktoken, "get_encoding", fail)

    assert usage.estimate_tokens("长夜灯火") == 4
    assert usage.estimate_tokens("") == 0
    usage._get_encoder.cache_clear()


def test_falls_back_to_character_count_when_encoding_fails(monkeypatch: Any) -> None:
    usage._get_encoder.cache_clear()
    monkeypatch.setattr(usage.tiktoken, "get_encoding", lambda _: BrokenEncoder())

    assert usage.estimate_tokens("长夜") == 2
    usage._get_encoder.cache_clear()
