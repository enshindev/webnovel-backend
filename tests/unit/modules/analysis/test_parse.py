from __future__ import annotations

from webnovel.modules.analysis.importing import parse_manuscript


def test_parse_txt_manuscript() -> None:
    assert "第一章" in parse_manuscript("book.txt", "第一章 雨夜".encode())
