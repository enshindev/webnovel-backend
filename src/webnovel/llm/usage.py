from __future__ import annotations

from functools import lru_cache
from typing import Any

import tiktoken


@lru_cache(maxsize=1)
def _get_encoder() -> Any | None:
    """首次用到再加载，避免 import 时联网下载编码表。"""
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _get_encoder()
    if encoder is None:
        return max(1, len(text))
    try:
        return len(encoder.encode(text))
    except Exception:
        return max(1, len(text))
