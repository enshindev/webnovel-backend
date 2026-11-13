from __future__ import annotations

from webnovel.modules.memory.chunking import chunk_text


def test_chunk_text_empty() -> None:
    assert chunk_text("   ") == []


def test_chunk_text_keeps_order_and_overlap() -> None:
    text = "\n".join(f"第{index}段。" + "字" * 120 for index in range(20))
    chunks = chunk_text(text, size=300, overlap=50)
    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)
    assert chunks[0].startswith("第0段")
    assert chunks[-1].endswith("字")
