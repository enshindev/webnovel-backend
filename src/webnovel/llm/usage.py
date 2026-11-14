from __future__ import annotations

import hashlib
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import tiktoken

_ENCODING_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
_ENCODING_SHA256 = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"


def _encoding_cache_path() -> Path:
    cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR") or os.environ.get("DATA_GYM_CACHE_DIR")
    if not cache_dir:
        cache_dir = str(Path(tempfile.gettempdir()) / "data-gym-cache")
    key = hashlib.sha1(_ENCODING_URL.encode()).hexdigest()
    return Path(cache_dir) / key


def _encoding_is_valid(path: Path) -> bool:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == _ENCODING_SHA256
    except OSError:
        return False


@lru_cache(maxsize=1)
def _get_encoder() -> Any | None:
    """只用本地已缓存的编码表，避免首次调用时联网下载。"""
    path = _encoding_cache_path()
    if not path.is_file() or not _encoding_is_valid(path):
        return None
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
