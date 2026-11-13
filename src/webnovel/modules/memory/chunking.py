from __future__ import annotations


def chunk_text(text: str, *, size: int = 1_000, overlap: int = 100) -> list[str]:
    """按字符切块，优先在换行/句号处断开；带少量重叠。"""
    normalized = text.strip()
    if not normalized:
        return []
    if size <= overlap:
        raise ValueError("size must be greater than overlap")

    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + size, length)
        if end < length:
            window_start = start + size // 2
            boundary = max(
                normalized.rfind("\n", window_start, end),
                normalized.rfind("。", window_start, end),
            )
            if boundary > start:
                end = boundary + 1
        chunks.append(normalized[start:end])
        if end >= length:
            break
        start = max(start + 1, end - overlap)
    return chunks
