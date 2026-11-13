from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FileStore(Protocol):
    async def put(self, key: str, data: bytes) -> str: ...

    async def get(self, key: str) -> bytes: ...


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    async def put(self, key: str, data: bytes) -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    async def get(self, key: str) -> bytes:
        return (self._root / key).read_bytes()
