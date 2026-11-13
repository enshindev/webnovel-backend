from __future__ import annotations

from typing import Any

import tiktoken

try:
    _ENCODER: Any = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - offline tiktoken data
    _ENCODER = None


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    if _ENCODER is None:
        return max(1, len(text))
    return len(_ENCODER.encode(text))
